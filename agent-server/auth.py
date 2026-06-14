import base64
import hashlib
import hmac
import logging
import os
import urllib.parse
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

print(
    f"AUTH_INIT: secret_len={len(BETTER_AUTH_SECRET)} "
    f"secret_start={BETTER_AUTH_SECRET[:8] if BETTER_AUTH_SECRET else 'EMPTY'} "
    f"db_set={bool(DATABASE_URL)}",
    flush=True,
)


def _unsign_hono(signed_value: str, secret: str) -> str | None:
    """Extract original value from a better-call/Hono-style signed cookie.

    Format: ``decodeURIComponent(value + "." + standard_base64(hmac-sha256(secret, value)))``
    """
    decoded = urllib.parse.unquote(signed_value)
    parts = decoded.rsplit(".", 1)
    if len(parts) != 2:
        logger.debug("unsign_hono: no dot found in decoded=%r (raw=%r)", decoded[:60], signed_value[:60])
        return None
    value, signature = parts
    expected = base64.b64encode(
        hmac.new(secret.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).digest()
    ).decode("ascii")
    if hmac.compare_digest(signature, expected):
        return value
    logger.debug("unsign_hono: sig mismatch value=%r signature=%r expected=%r", value, signature, expected)
    return None


def _lookup_session(token: str) -> str | None:
    """Look up a session by token or id in the database. Returns userId or None."""
    if not DATABASE_URL:
        return None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    'SELECT "userId", "expiresAt" FROM session WHERE token = %s OR id = %s',
                    (token, token),
                )
                row = cur.fetchone()
                if row:
                    user_id, expires_at = row
                    if expires_at and expires_at.replace(tzinfo=UTC) < datetime.now(UTC):
                        raise AuthFailedError("Session has expired. Please log in again.")
                    return user_id
    except AuthFailedError:
        raise
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

    logger.info("Validating session token, len=%d", len(raw_token))

    # 1) Try direct JWT decode (standard 3-segment JWT)
    if BETTER_AUTH_SECRET:
        try:
            payload = jwt.decode(
                raw_token,
                BETTER_AUTH_SECRET,
                algorithms=["HS256"],
                options={"verify_exp": False},
            )
            user_id = payload.get("sub")
            if user_id:
                logger.info("JWT auth OK for user=%s", user_id)
                return user_id
        except Exception:
            pass

    # 2) Try Hono-style signed cookie: token.base64url_hmac
    if BETTER_AUTH_SECRET:
        unsigned = _unsign_hono(raw_token, BETTER_AUTH_SECRET)
        if unsigned:
            user_id = _lookup_session(unsigned)
            if user_id:
                logger.info("Signed-cookie auth OK for user=%s", user_id)
                return user_id
            logger.info("Unsigned OK but no DB row for token len=%d", len(unsigned))

    # 3) Direct DB lookup (legacy / raw token from other sources)
    user_id = _lookup_session(raw_token)
    if user_id:
        logger.info("Direct DB auth OK for user=%s", user_id)
        return user_id

    raise AuthFailedError("Invalid or expired session. Please log in again.")
