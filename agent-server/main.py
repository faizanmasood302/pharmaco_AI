from __future__ import annotations

import logging
import os
import uuid
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from logging_config import setup_logging, request_id_var

# Initialize rate limiter
def get_user_or_ip(request: Request):
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        return auth.split(" ")[1]
    return get_remote_address(request)

limiter = Limiter(key_func=get_user_or_ip)

# Initialize production structured logging
setup_logging()
logger = logging.getLogger(__name__)

from agents.adherence import process_check_in, start_adherence_monitoring
from agents.orchestrator import orchestrate
from agents.reporter import generate_clinical_note
from agents.therapy_orchestrator import orchestrate_therapy_generation
from auth import create_token, verify_token
from db.supabase import (
    get_clinical_reports_by_patient,
    is_configured,
    update_evaluation_decision,
    update_therapy_decision,
    list_all_patients,
    list_evaluations,
    list_medications,
    save_clinical_report,
    save_therapy_generation,
    upsert_patient,
)
from exceptions import AuthFailedError, InternalServerError, PharmacogenomicError
from fhir.parser import parse_fhir_bundle
# setup_logging and request_id_var already imported above
from models import (
    AdherencePlanRequest,
    CheckInSubmitRequest,
    EvaluationResponse,
    FhirIngestRequest,
    PrescriptionRequest,
    TherapyGenerationRequest,
    TherapyGenerationResponse,
    ReviewDecisionRequest,
)
from pgx.rules import DRUG_RULES

app = FastAPI(
    title="Pharmacogenomic Agent Server",
    description="AI agent harness for n-of-1 prescribing decisions",
    version="0.2.0",
    openapi_url="/api/openapi.json",
    docs_url="/api/docs"
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# Allowed origins from environment
ALLOWED_ORIGINS = os.environ.get(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-Requested-With"
    ],
    max_age=3600,  # Cache preflight 1 hour
)

@app.exception_handler(PharmacogenomicError)
async def pgx_exception_handler(request: Request, exc: PharmacogenomicError):
    req_id = request_id_var.get()
    
    logger.error(
        f"Pharmacogenomic error: {exc.code.value}",
        extra={
            "request_id": req_id,
            "error_code": exc.code.value,
            "status_code": exc.status_code,
            "retriable": exc.retriable
        }
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code.value,
                "message": exc.message,
                "request_id": req_id,
                "retriable": exc.retriable,
                "details": exc.details
            }
        }
    )

@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    """Middleware to inject and track a unique request ID for observability."""
    req_id = str(uuid.uuid4())
    request_id_var.set(req_id)
    
    # Log request start
    logger.info("Incoming API request", extra={
        "method": request.method,
        "path": request.url.path,
        "client_ip": request.client.host if request.client else None
    })
    
    response = await call_next(request)
    response.headers["X-Request-ID"] = req_id
    return response


@app.get("/")
@limiter.limit("20/minute")
async def root(request: Request):
    return {
        "message": "Pharmacogenomic Agent Server is running",
        "supabase_configured": is_configured(),
        "endpoints": {
            "evaluate": "POST /api/evaluate-prescription",
            "patients": "GET /api/patients",
            "ingest_fhir": "POST /api/ingest-fhir",
            "evaluations": "GET /api/evaluations/{patient_id}",
            "evaluation_decision": "POST /api/evaluations/{evaluation_id}/decision",
            "adherence": "POST /api/adherence/plans",
            "check_in": "POST /api/adherence/check-ins/{check_in_id}",
            "medications": "GET /api/medications",
            "clinical_reports": "POST /api/clinical-reports",
            "patient_reports": "GET /api/patients/{patient_id}/reports",
        },
    }


@app.get("/api/medications")
@limiter.limit("20/minute")
async def list_medications_endpoint(request: Request, user_id: str = Depends(verify_token)):
    meds = list_medications()
    if not meds:
        # Fallback to demo defaults if DB is empty or unreachable
        return {
            "medications": [
                {
                    "name": rule.name,
                    "enzyme": rule.enzyme,
                    "is_prodrug": rule.is_prodrug
                }
                for rule in DRUG_RULES.values()
            ]
        }
    return {"medications": meds}


class ClinicalReportRequest(BaseModel):
    evaluation_id: str
    patient_id: str
    content: str


@app.post("/api/clinical-reports")
@limiter.limit("20/minute")
async def create_clinical_report(
    request: Request,
    payload: ClinicalReportRequest,
    user_id: str = Depends(verify_token),
):
    try:
        report_id = save_clinical_report(
            payload.evaluation_id,
            payload.patient_id,
            payload.content,
            clinician_id=user_id,
        )
        if not report_id:
            raise HTTPException(status_code=500, detail="Failed to save clinical report")

        from audit import log_audit

        log_audit(
            user_id=user_id,
            action="SAVE_CLINICAL_REPORT",
            patient_id=payload.patient_id,
            resource_id=report_id,
            details={"evaluation_id": payload.evaluation_id},
            request=request,
        )

        return {"report_id": report_id, "status": "saved"}
    except Exception as e:
        logger.error(f"Clinical report save failed: {e}")
        raise InternalServerError(f"Report save failed: {str(e)}")


@app.get("/api/patients/{patient_id}/reports")
@limiter.limit("20/minute")
async def list_patient_reports_endpoint(
    request: Request,
    patient_id: str,
    user_id: str = Depends(verify_token),
):
    reports = get_clinical_reports_by_patient(patient_id)
    return {"reports": reports}


@app.get("/api/patients")
@limiter.limit("20/minute")
async def list_patients(request: Request, user_id: str = Depends(verify_token)):
    patients = list_all_patients()
    return {
        "patients": [
            {
                "id": p["id"],
                "display_name": p["display_name"],
                "indication": p["indication"],
                "phenotype": p["cyp_profiles"][0]["phenotype"] if p["cyp_profiles"] else "Unknown",
            }
            for p in patients
        ]
    }


@app.get("/api/evaluations/{patient_id}")
async def get_evaluations(
    patient_id: str, 
    limit: int = 10,
    user_id: str = Depends(verify_token)
):
    # Normalized ID casing - Fix #3.4
    rows = list_evaluations(patient_id.upper(), limit=limit)
    return {
        "evaluations": [
            {
                "id": row.get("id"),
                "patient_id": row.get("patient_id"),
                "medication": row.get("medication"),
                "flagged": row.get("flagged"),
                "risk_level": row.get("risk_level"),
                "created_at": row.get("created_at"),
                "result_json": row.get("result_json"),
            }
            for row in rows
        ]
    }


@app.post("/api/ingest-fhir")
@limiter.limit("10/minute")
async def ingest_fhir(
    request: Request,
    payload: FhirIngestRequest,
    user_id: str = Depends(verify_token)
):
    try:
        patient = parse_fhir_bundle(payload.bundle)
        if not patient["id"].startswith("PGX"):
            patient["id"] = f"PGX-{patient['id']}"[:20]
        upserted = upsert_patient(patient)
        return {
            "status": "success",
            "patient_id": upserted["id"],
            "display_name": upserted["display_name"],
            "phenotype": upserted["cyp_profiles"][0]["phenotype"] if upserted["cyp_profiles"] else "Unknown",
        }
    except Exception as e:
        logger.error(f"FHIR ingestion failed: {e}")
        raise InternalServerError(f"FHIR ingestion failed: {str(e)}")


class LoginRequest(BaseModel):
    email: str
    password: str

@app.post("/api/auth/login")
@limiter.limit("5/minute")
async def login(login_request: LoginRequest, request: Request):
    # Fixed Bug #1.5: Actual credential verification with hashing
    from config import DEMO_DOCTORS
    import hashlib
    
    hashed_input = hashlib.sha256(login_request.password.encode()).hexdigest()
    expected_hashed = DEMO_DOCTORS.get(login_request.email)
    
    if expected_hashed and expected_hashed == hashed_input:
        token = create_token(user_id=login_request.email)
        return {"access_token": token, "token_type": "bearer"}
    
    logger.warning(f"Failed login attempt for {login_request.email}")
    raise AuthFailedError("Invalid email or password")

@app.post("/api/evaluate-prescription", response_model=EvaluationResponse)
@limiter.limit("10/minute")
async def evaluate_prescription(
    eval_request: PrescriptionRequest,
    request: Request,
    user_id: str = Depends(verify_token)
):
    logger.info(
        "Initiating prescription evaluation", 
        extra={
            "patient_id": eval_payload.patient_id, 
            "medication": eval_payload.medication,
            "user_id": user_id
        }
    )
    
    # Normalized ID casing for audit - Fix M9
    patient_id_normalized = eval_payload.patient_id.upper()
    
    result = orchestrate(patient_id_normalized, eval_payload.medication)
    
    # Log the access to the patient's data
    from audit import log_audit
    log_audit(
        user_id=user_id,
        action="EVALUATE_PRESCRIPTION",
        patient_id=patient_id_normalized,
        resource_id=result.medication,
        details={
            "medication": eval_payload.medication,
            "flagged": result.flagged,
            "risk_level": result.risk_level
        },
        request=request
    )

    logger.info(
        "Evaluation complete", 
        extra={
            "patient_id": patient_id_normalized,
            "medication": eval_payload.medication,
            "flagged": result.flagged,
            "risk_level": result.risk_level,
            "user_id": user_id
        }
    )
    return result


@app.post("/api/clinical-note")
@limiter.limit("10/minute")
async def create_note(
    request: Request,
    result: EvaluationResponse,
    _user_id: str = Depends(verify_token),
):
    try:
        if result.human_gate.status != "approved":
            raise HTTPException(
                status_code=409,
                detail="Clinical note generation requires an approved human gate.",
            )
        # Pass the Pydantic model directly to the generator
        note = generate_clinical_note(result)
        return {"note": note}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/adherence/plans")
@limiter.limit("20/minute")
async def create_adherence_plan(
    request: Request,
    payload: AdherencePlanRequest,
    _user_id: str = Depends(verify_token),
):
    try:
        plan = start_adherence_monitoring(payload.patient_id, payload.medication)
        if plan.get("status") == "error":
            raise HTTPException(
                status_code=500,
                detail=plan.get("message", "Could not create adherence plan"),
            )
        return plan
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/adherence/check-ins/{check_in_id}")
async def submit_check_in(
    check_in_id: str, 
    request: CheckInSubmitRequest,
    user_id: str = Depends(verify_token)
):
    try:
        # Fixed: Corrected parameter names to match process_check_in signature
        result = process_check_in(check_in_id, payload.response, payload.side_effect_reported)
        if result.get("status") == "error":
            raise HTTPException(
                status_code=404,
                detail=result.get("message", "Check-in not found"),
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Check-in submission failed: {e}")
        raise InternalServerError(f"Check-in submission failed: {str(e)}")


@app.post("/api/evaluations/{evaluation_id}/decision")
@limiter.limit("20/minute")
async def review_evaluation_decision(
    request: Request,
    evaluation_id: str,
    payload: ReviewDecisionRequest,
    user_id: str = Depends(verify_token),
):
    decision = payload.decision.lower().strip()
    logger.info(f"Clinician decision received: {decision} for {evaluation_id}")
    if decision not in {"approved", "rejected"}:
        raise HTTPException(status_code=400, detail="decision must be 'approved' or 'rejected'")

    try:
        updated = update_evaluation_decision(
            evaluation_id,
            decision,
            reviewer=payload.reviewer or user_id,
            rationale=payload.rationale,
        )
        if not updated:
            logger.warning(f"Evaluation {evaluation_id} not found for decision update")
            raise HTTPException(status_code=404, detail="Evaluation not found")

        from audit import log_audit

        log_audit(
            user_id=user_id,
            action="REVIEW_EVALUATION",
            resource_id=evaluation_id,
            details={
                "decision": decision,
                "reviewer": payload.reviewer or user_id,
                "rationale": payload.rationale,
            },
            request=request,
        )

        # Return the updated result_json for frontend state sync
        result_json = updated.get("result_json", updated)
        logger.info(f"Decision {decision} saved for {evaluation_id}")
        return {
            "evaluation_id": evaluation_id,
            "decision": decision,
            "evaluation": result_json,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Evaluation decision update failed: {e}")
        raise InternalServerError(f"Decision update failed: {str(e)}")


@app.post("/api/therapy-requests/{therapy_request_id}/decision")
@limiter.limit("20/minute")
async def review_therapy_decision(
    request: Request,
    therapy_request_id: str,
    payload: ReviewDecisionRequest,
    user_id: str = Depends(verify_token),
):
    decision = payload.decision.lower().strip()
    if decision not in {"approved", "rejected"}:
        raise HTTPException(status_code=400, detail="decision must be 'approved' or 'rejected'")

    try:
        updated = update_therapy_decision(
            therapy_request_id,
            decision,
            reviewer=payload.reviewer or user_id,
            rationale=payload.rationale,
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Therapy request not found")

        from audit import log_audit

        log_audit(
            user_id=user_id,
            action="REVIEW_THERAPY_RESEARCH",
            resource_id=therapy_request_id,
            details={
                "decision": decision,
                "reviewer": payload.reviewer or user_id,
                "rationale": payload.rationale,
            },
            request=request,
        )

        return {
            "therapy_request_id": therapy_request_id,
            "decision": decision,
            "result": updated.get("result_json", updated),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Therapy decision update failed: {e}")
        raise InternalServerError(f"Decision update failed: {str(e)}")


@app.post("/api/generate-therapy", response_model=TherapyGenerationResponse)
@limiter.limit("5/minute")
async def generate_therapy_endpoint(
    eval_request: TherapyGenerationRequest,
    request: Request,
    user_id: str = Depends(verify_token)
):
    logger.info(
        "Initiating therapy generation", 
        extra={
            "patient_id": eval_payload.patient_id, 
            "target_disease": eval_request.target_disease,
            "user_id": user_id
        }
    )
    
    patient_id_normalized = eval_payload.patient_id.upper()
    result = orchestrate_therapy_generation(
        patient_id_normalized,
        eval_request.target_disease,
        eval_request.max_iterations,
    )
    result.therapy_request_id = save_therapy_generation(result.model_dump())
    
    # Audit log
    from audit import log_audit
    log_audit(
        user_id=user_id,
        action="GENERATE_THERAPY",
        patient_id=patient_id_normalized,
        resource_id=result.target_disease,
        details={
            "status": result.status,
            "iterations": result.iterations,
            "toxicity_score": result.toxicity_score
        },
        request=request
    )

    logger.info(
        "Generation complete", 
        extra={
            "patient_id": patient_id_normalized,
            "status": result.status,
            "user_id": user_id
        }
    )
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
