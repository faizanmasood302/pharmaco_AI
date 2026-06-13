import logging
from datetime import UTC, datetime

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from db.supabase import get_admin_client
from exceptions import AuthFailedError

security = HTTPBearer()
logger = logging.getLogger(__name__)


def verify_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str:
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
    token = raw_token.strip().strip('"').strip("'").split(".")[0]

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
                logger.warning(
                    f"Failed to parse session expiry {expires_at_raw}: {parse_err}"
                )
                raise AuthFailedError(
                    "Session validation error. Please log in again."
                ) from parse_err

        user_id = result.data.get("userId")
        if not user_id:
            logger.warning("Session found but no userId present")
            raise AuthFailedError("Invalid session data. Please log in again.")

        return user_id
    except AuthFailedError:
        raise
    except Exception as exc:
        logger.error(f"Session verification failed: {exc}", exc_info=True)
        raise AuthFailedError("Authentication error. Please log in again.") from exc
