import logging
import os
from datetime import UTC, datetime

import psycopg2
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from db.supabase import get_admin_client
from exceptions import AuthFailedError

security = HTTPBearer()
logger = logging.getLogger(__name__)


def _verify_via_supabase(token: str) -> str | None:
    supabase = get_admin_client()
    if not supabase:
        return None
    try:
        result = (
            supabase.table("session")
            .select("userId, expiresAt")
            .eq("token", token)
            .maybe_single()
            .execute()
        )
        if not result or not result.data:
            return None

        expires_at_raw = result.data.get("expiresAt")
        if expires_at_raw:
            from dateutil import parser

            try:
                if isinstance(expires_at_raw, (int, float)):
                    expires_at = datetime.fromtimestamp(expires_at_raw / 1000, UTC)
                else:
                    expires_at = parser.isoparse(str(expires_at_raw))
                if expires_at < datetime.now(UTC):
                    logger.info(
                        f"Supabase session expired for user {result.data.get('userId')}"
                    )
                    return None
            except Exception:
                return None

        user_id = result.data.get("userId")
        return user_id
    except Exception as exc:
        logger.warning("Supabase session verification failed: %s", exc)
        return None


def _verify_via_local_pg(token: str) -> str | None:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        return None
    try:
        conn = psycopg2.connect(db_url)
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    'SELECT "userId", "expiresAt" FROM session WHERE token = %s',
                    (token,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                user_id, expires_at = row
                if expires_at and expires_at.replace(tzinfo=UTC) < datetime.now(UTC):
                    logger.info(f"Local session expired for user {user_id}")
                    return None
                return user_id
    except Exception as exc:
        logger.warning("Local PG session verification failed: %s", exc)
        return None


def verify_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str:
    if not credentials or not credentials.credentials:
        raise AuthFailedError("Authorization header missing or malformed")

    raw_token = credentials.credentials
    token = raw_token.strip().strip('"').strip("'").split(".")[0]

    logger.info("Validating session token")

    if not token:
        raise AuthFailedError("Session token cannot be empty")

    user_id = _verify_via_supabase(token)
    if user_id:
        return user_id

    user_id = _verify_via_local_pg(token)
    if user_id:
        return user_id

    raise AuthFailedError("Invalid or expired session. Please log in again.")
