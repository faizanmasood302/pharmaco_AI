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
    request: Request | None = None,
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
                "details": details,
            },
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
            extra={"error": str(e), "attempted_record": audit_record},
            exc_info=True,
        )
