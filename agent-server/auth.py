import uuid
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import ALGORITHM, SECRET_KEY
from exceptions import AuthFailedError

security = HTTPBearer()

if not SECRET_KEY:
    # We provide a loud failure on startup to prevent insecure deployments
    raise ValueError(
        "SECRET_KEY environment variable is not set. "
        "This is required for JWT token generation. "
        "Generate one with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
    )

def create_token(user_id: str, expires_delta: timedelta = timedelta(hours=1)) -> str:
    """Create JWT token for user with unique ID and default role."""
    payload = {
        "sub": user_id,
        "jti": str(uuid.uuid4()),
        "role": "doctor", # Default role for clinical harness
        "exp": datetime.now(UTC) + expires_delta,
        "iat": datetime.now(UTC)
    }
    encoded = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return encoded

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Verify JWT token and return user_id"""
    try:
        payload = jwt.decode(
            credentials.credentials,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise AuthFailedError("Could not validate credentials")
        return user_id
    except jwt.ExpiredSignatureError:
        raise AuthFailedError("Token expired")
    except jwt.InvalidTokenError:
        raise AuthFailedError("Invalid token")
