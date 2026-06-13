 Backend Codebase (Auth, Security, API)

This file contains the backend security, authentication, and core API perimeter.

## Authentication Logic (`agent-server/auth.py`)
```python
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import SUPABASE_URL, SUPABASE_ANON_KEY
from exceptions import AuthFailedError
from db.supabase import get_admin_client

security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials | None = Depends(security)) -> str:
    """
    Verify BetterAuth session token against the Supabase database.
    BetterAuth session tokens are opaque strings stored in the 'session' table.
    
    Security Notes:
    - Tokens are validated server-side against the Supabase session table
    - Expired sessions are rejected
    - Invalid tokens receive generic error messages (no information leakage)
    """
    if not credentials or not credentials.credentials:
        raise AuthFailedError("Authorization header missing or malformed")
    
    raw_token = credentials.credentials
    # BetterAuth tokens can be signed (value.signature). 
    # The DB only stores the 'value' part before the first dot.
    token = raw_token.strip().strip('"').strip("'").split('.')[0]
    
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info("Validating session token")

    if not token:
        raise AuthFailedError("Session token cannot be empty")

    supabase = get_admin_client()
    if not supabase:
        raise AuthFailedError("Authentication service unavailable")

    try:
        # Query the session table using the parsed base token
        result = (
            supabase.table("session")
            .select("userId, expiresAt")
            .eq("token", token)
            .maybe_single()
            .execute()
        )

        if not result or not result.data:
            logger.warning("Session not found or expired")
            raise AuthFailedError("Invalid or expired session. Please log in again.")

        # Check expiration
        expires_at_raw = result.data.get("expiresAt")
        if expires_at_raw:
            from dateutil import parser
            try:
                if isinstance(expires_at_raw, (int, float)):
                    expires_at = datetime.fromtimestamp(expires_at_raw / 1000, UTC)
                else:
                    expires_at = parser.isoparse(str(expires_at_raw))
                
                if expires_at < datetime.now(UTC):
                    logger.info(f"Session expired for user {result.data.get('userId')}")
                    raise AuthFailedError("Session expired. Please log in again.")
            except AuthFailedError:
                raise
            except Exception as parse_err:
                logger.warning(f"Failed to parse session expiry {expires_at_raw}: {parse_err}")
                raise AuthFailedError("Session validation error. Please log in again.")

        user_id = result.data.get("userId")
        if not user_id:
            logger.warning("Session found but no userId present")
            raise AuthFailedError("Invalid session data. Please log in again.")

        return user_id
    except AuthFailedError:
        raise
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Session verification failed: {e}", exc_info=True)
        raise AuthFailedError("Authentication error. Please log in again.")


# create_token is no longer used as BetterAuth handles session generation
def create_token(user_id: str, expires_delta: timedelta = timedelta(hours=1)) -> str:
    return "deprecated"
```

## Crypto Utility (`agent-server/crypto.py`)
```python
import logging
import os

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

# In a true production environment, this key would be fetched via AWS KMS or HashiCorp Vault.
# For this MVP, we pull from the environment or generate an ephemeral dev key.
_key = os.environ.get("ENCRYPTION_KEY")

if not _key:
    logger.warning("No ENCRYPTION_KEY found in environment. Generating ephemeral key for local development.")
    _key = Fernet.generate_key().decode()
    os.environ["ENCRYPTION_KEY"] = _key

_cipher_suite = Fernet(_key.encode())

def encrypt_pii(plaintext: str) -> str:
    """Encrypts a string using Fernet symmetric encryption."""
    if not plaintext:
        return ""
    try:
        return _cipher_suite.encrypt(plaintext.encode()).decode()
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        raise ValueError("Failed to encrypt sensitive data")

def decrypt_pii(ciphertext: str) -> str:
    """Decrypts a Fernet encrypted string."""
    if not ciphertext:
        return ""
    try:
        return _cipher_suite.decrypt(ciphertext.encode()).decode()
    except Exception as e:
        logger.warning(f"Decryption failed. Falling back to plaintext (for seed data). {e}")
        return ciphertext
```

## Audit Logging (`agent-server/audit.py`)
```python
import logging
from typing import Any

from fastapi import Request

from db.supabase import _client as supabase_client

logger = logging.getLogger(__name__)

def log_audit(
    user_id: str,
    action: str,
    patient_id: str | None = None,
    resource_id: str | None = None,
    details: dict[str, Any] | None = None,
    request: Request | None = None
) -> None:
    """
    Records a HIPAA-compliant audit event to the database.
    This function is designed to never fail the main execution thread;
    it catches its own exceptions and logs them to stderr if the DB is unreachable.
    """
    if supabase_client is None:
        # If running in local/demo mode without Supabase, just emit structured logs.
        logger.info(
            "Audit event (Local Mode)",
            extra={
                "audit_action": action,
                "user_id": user_id,
                "patient_id": patient_id,
                "resource_id": resource_id,
                "details": details
            }
        )
        return

    try:
        ip_address = None
        user_agent = None
        
        if request:
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")
        
        audit_record = {
            "user_id": user_id,
            "action": action,
            "patient_id": patient_id,
            "resource_id": resource_id,
            "details": details or {},
            "ip_address": ip_address,
            "user_agent": user_agent,
        }
        
        supabase_client.table("audit_logs").insert(audit_record).execute()
        
    except Exception as e:
        # CRITICAL: We must not break the clinical flow just because logging failed,
        # but we must loudly report the failure for DevOps.
        logger.error(
            "CRITICAL: Failed to write to audit_logs table",
            extra={
                "error": str(e),
                "attempted_record": audit_record
            },
            exc_info=True
        )
```

## Main API Perimeter (`agent-server/main.py`)
```python
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
```
*(Remainder of main.py truncated for brevity in this documentation file)*
