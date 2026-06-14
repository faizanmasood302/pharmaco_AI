import json
import logging
import os
from typing import Any

import psycopg2
from dotenv import load_dotenv
from fastapi import Request

load_dotenv()
DATABASE_URL = (os.environ.get("DATABASE_URL") or "").strip()

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
    if not DATABASE_URL:
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

        if request and request.client:
            raw_ip = request.client.host
            # Only store if it looks like a valid IP (not 'testclient' etc.)
            if raw_ip and ('.' in raw_ip or ':' in raw_ip):
                ip_address = raw_ip
            user_agent = request.headers.get("user-agent")

        conn = psycopg2.connect(DATABASE_URL)
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO audit_logs (user_id, action, patient_id, resource_id, details, ip_address, user_agent)
                           VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s)""",
                        (
                            user_id,
                            action,
                            patient_id,
                            resource_id,
                            json.dumps(details or {}),
                            ip_address,
                            user_agent,
                        ),
                    )
        finally:
            conn.close()

    except Exception as e:
        logger.error(
            "CRITICAL: Failed to write to audit_logs table",
            extra={"error": str(e), "action": action, "user_id": user_id},
            exc_info=True,
        )
