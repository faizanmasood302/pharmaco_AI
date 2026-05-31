from __future__ import annotations

import logging
import os
import uuid

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from agents.adherence import process_check_in, start_adherence_monitoring
from agents.orchestrator import orchestrate
from agents.reporter import generate_clinical_note
from auth import create_token, verify_token
from db.supabase import (
    is_configured,
    list_all_patients,
    list_evaluations,
    upsert_patient,
)
from exceptions import PharmacogenomicError
from fhir.parser import parse_fhir_bundle
from logging_config import setup_logging, request_id_var
from models import (
    AdherencePlanRequest,
    CheckInSubmitRequest,
    EvaluationResponse,
    FhirIngestRequest,
    PrescriptionRequest,
)
from pgx.rules import DRUG_RULES

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Initialize production structured logging
setup_logging()
logger = logging.getLogger(__name__)

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
async def root():
    return {
        "message": "Pharmacogenomic Agent Server is running",
        "supabase_configured": is_configured(),
        "endpoints": {
            "evaluate": "POST /api/evaluate-prescription",
            "patients": "GET /api/patients",
            "ingest_fhir": "POST /api/ingest-fhir",
            "evaluations": "GET /api/evaluations/{patient_id}",
            "adherence": "POST /api/adherence/plans",
            "check_in": "POST /api/adherence/check-ins/{check_in_id}",
            "medications": "GET /api/medications",
        },
    }


@app.get("/api/medications")
async def list_medications(user_id: str = Depends(verify_token)):
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


@app.get("/api/patients")
async def list_patients(user_id: str = Depends(verify_token)):
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
async def ingest_fhir(
    request: FhirIngestRequest,
    user_id: str = Depends(verify_token)
):
    try:
        patient = parse_fhir_bundle(request.bundle)
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
        raise HTTPException(status_code=400, detail=str(e))


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
            "patient_id": eval_request.patient_id, 
            "medication": eval_request.medication,
            "user_id": user_id
        }
    )
    
    # Normalized ID casing for audit - Fix M9
    patient_id_normalized = eval_request.patient_id.upper()
    
    result = orchestrate(patient_id_normalized, eval_request.medication)
    
    # Log the access to the patient's data
    from audit import log_audit
    log_audit(
        user_id=user_id,
        action="EVALUATE_PRESCRIPTION",
        patient_id=patient_id_normalized,
        resource_id=result.medication,
        details={
            "medication": eval_request.medication,
            "flagged": result.flagged,
            "risk_level": result.risk_level
        },
        request=request
    )

    logger.info(
        "Evaluation complete", 
        extra={
            "patient_id": patient_id_normalized,
            "medication": eval_request.medication,
            "flagged": result.flagged,
            "risk_level": result.risk_level,
            "user_id": user_id
        }
    )
    return result


@app.post("/api/clinical-note")
async def create_note(result: EvaluationResponse):
    try:
        # Pass the Pydantic model directly to the generator
        note = generate_clinical_note(result)
        return {"note": note}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/adherence/plans")
async def create_adherence_plan(request: AdherencePlanRequest):
    try:
        plan = start_adherence_monitoring(request.patient_id, request.medication)
        return plan
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
        result = process_check_in(check_in_id, request.response, request.side_effect_reported)
        return result
    except Exception as e:
        logger.error(f"Check-in submission failed: {e}")
        raise InternalServerError(f"Check-in submission failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
