import uuid
from datetime import UTC, datetime, timedelta

from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import SUPABASE_URL, SUPABASE_ANON_KEY
from exceptions import AuthFailedError
from db.supabase import get_supabase_client

security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """
    Verify BetterAuth session token against the Supabase database.
    BetterAuth session tokens are opaque strings stored in the 'session' table.
    """
    token = credentials.credentials
    if not token:
        raise AuthFailedError("Session token missing")

    supabase = get_supabase_client()
    if not supabase:
        # Fallback for local dev if Supabase isn't configured
        # Note: In production, this would be a hard failure.
        import os
        if os.environ.get("ENV") == "development":
            return "demo-user"
        raise AuthFailedError("Authentication system unavailable")

    try:
        # Query the BetterAuth session table
        # BetterAuth table names are usually "session" and "user"
        result = (
            supabase.table("session")
            .select("userId, expiresAt")
            .eq("token", token)
            .single()
            .execute()
        )

        if not result.data:
            raise AuthFailedError("Invalid or expired session")

        # Check expiration
        # BetterAuth stores expiresAt as an ISO string or timestamp
        expires_at_str = result.data.get("expiresAt")
        if expires_at_str:
            # Handle potential different formats (BetterAuth defaults to ISO string)
            from dateutil import parser
            expires_at = parser.isoparse(expires_at_str)
            if expires_at < datetime.now(UTC):
                raise AuthFailedError("Session expired")

        return result.data.get("userId")
    except AuthFailedError:
        raise
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Session verification failed: {e}")
        raise AuthFailedError("Internal authentication error")


# create_token is no longer used as BetterAuth handles session generation
def create_token(user_id: str, expires_delta: timedelta = timedelta(hours=1)) -> str:
    return "deprecated"
