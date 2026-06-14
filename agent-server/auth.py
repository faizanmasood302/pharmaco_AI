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


def _verify_session_jwt(jwt_token: str) -> str | None:
    if not BETTER_AUTH_SECRET:
        logger.warning("BETTER_AUTH_SECRET not set, falling back to DB lookup")
        return _verify_session_db(jwt_token)
    try:
        payload = jwt.decode(
            jwt_token,
            BETTER_AUTH_SECRET,
            algorithms=["HS256"],
            options={"verify_exp": False},
        )
        token = payload.get("token") or payload.get("sub")
        if not token:
            return None
        return _verify_session_db(token)
    except Exception as exc:
        logger.warning("JWT verification failed: %s", exc)
        return _verify_session_db(jwt_token)


def _verify_session_db(token: str) -> str | None:
    if not DATABASE_URL:
        return None
    try:
        conn = psycopg2.connect(DATABASE_URL)
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
                    logger.info("Session expired for user %s", user_id)
                    return None
                return user_id
    except Exception as exc:
        logger.warning("DB session verification failed: %s", exc)
        return None


def verify_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str:
    if not credentials or not credentials.credentials:
        raise AuthFailedError("Authorization header missing or malformed")

    raw_token = credentials.credentials.strip().strip('"').strip("'")

    if not raw_token:
        raise AuthFailedError("Session token cannot be empty")

    logger.info("Validating session token")

    user_id = _verify_session_jwt(raw_token)
    if user_id:
        return user_id

    raise AuthFailedError("Invalid or expired session. Please log in again.")
