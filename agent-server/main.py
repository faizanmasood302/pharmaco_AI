import logging
import os
import uuid

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from logging_config import request_id_var, setup_logging


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
from agents.orchestrator import evaluate_prescription as orchestrate
from agents.reporter import generate_clinical_note
from auth import verify_token
from db.database import (
    get_clinical_reports_by_patient,
    is_configured,
    list_all_patients,
    list_evaluations,
    list_medications,
    save_clinical_report,
    update_evaluation_decision,
    upsert_patient,
)
from exceptions import InternalServerError, PharmacogenomicError
from fhir.parser import parse_fhir_bundle

# setup_logging and request_id_var already imported above
from models import (
    AdherencePlanRequest,
    CheckInSubmitRequest,
    EvaluationResponse,
    FhirIngestRequest,
    PrescriptionRequest,
    ReviewDecisionRequest,
)
from pgx.rules import DRUG_RULES

from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Warm up database on start; connect MCP servers; clean up on shutdown."""
    from agents.mcp_client import MCPClient
    await MCPClient.get_instance().connect_all()

    from db.database import warmup_database as _warmup
    import threading
    t = threading.Thread(target=_warmup, daemon=True)
    t.start()
    yield

    await MCPClient.get_instance().disconnect_all()


app = FastAPI(
    title="Pharmacogenomic Agent Server",
    description="AI agent harness for n-of-1 prescribing decisions",
    version="0.2.0",
    lifespan=lifespan,
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


@app.get("/api/health")
async def health():
    return {"status": "healthy"}


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
        raise InternalServerError(f"Report save failed: {str(e)}") from e


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
        raise InternalServerError(f"FHIR ingestion failed: {str(e)}") from e


@app.post("/api/evaluate-prescription", response_model=EvaluationResponse)
@limiter.limit("10/minute")
async def evaluate_prescription(
    eval_payload: PrescriptionRequest,
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
    
    result = await orchestrate(patient_id_normalized, eval_payload.medication)
    
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
        note = await generate_clinical_note(result)
        return {"note": note}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/adherence/check-ins/{check_in_id}")
async def submit_check_in(
    check_in_id: str, 
    payload: CheckInSubmitRequest,
    user_id: str = Depends(verify_token)
):
    try:
        # Fixed: Corrected parameter names to match process_check_in signature
        result = await process_check_in(check_in_id, payload.response, payload.side_effect_reported)
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
        raise InternalServerError(f"Check-in submission failed: {str(e)}") from e


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
        raise InternalServerError(f"Decision update failed: {str(e)}") from e


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

