import logging
import os
from datetime import UTC, datetime

import jwt
import psycopg2
from dotenv import load_dotenv
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from exceptions import AuthFailedError

load_dotenv()
security = HTTPBearer()
logger = logging.getLogger(__name__)

BETTER_AUTH_SECRET = (os.environ.get("BETTER_AUTH_SECRET") or "").strip()
DATABASE_URL = (os.environ.get("DATABASE_URL") or "").strip()


def verify_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str:
    if not credentials or not credentials.credentials:
        raise AuthFailedError("Authorization header missing or malformed")

    raw_token = credentials.credentials.strip().strip('"').strip("'")

    if not raw_token:
        raise AuthFailedError("Session token cannot be empty")

    logger.info("Validating session token")

    # Try JWT verification first (BetterAuth sends a JWT in the cookie)
    if BETTER_AUTH_SECRET:
        try:
            payload = jwt.decode(
                raw_token,
                BETTER_AUTH_SECRET,
                algorithms=["HS256"],
            )
            user_id = payload.get("sub")
            if user_id:
                return user_id
        except jwt.ExpiredSignatureError:
            raise AuthFailedError("Session has expired. Please log in again.")
        except Exception:
            pass

    # Fallback: look up raw token in session table
    if DATABASE_URL:
        try:
            conn = psycopg2.connect(DATABASE_URL)
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        'SELECT "userId", "expiresAt" FROM session WHERE token = %s',
                        (raw_token,),
                    )
                    row = cur.fetchone()
                    if row:
                        user_id, expires_at = row
                        if expires_at and expires_at.replace(tzinfo=UTC) < datetime.now(UTC):
                            raise AuthFailedError("Session has expired. Please log in again.")
                        return user_id
        except Exception as exc:
            logger.warning("DB session verification failed: %s", exc)

    raise AuthFailedError("Invalid or expired session. Please log in again.")
