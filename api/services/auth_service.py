"""
JWT Authentication Service.
"""

import logging
from datetime import datetime, timedelta, timezone

import jwt
from config import settings
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from services.setup_state import is_secret_key_safe, is_setup_complete

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24 * 7  # 1 week

security = HTTPBearer(auto_error=False)


def create_access_token(user_id: int, username: str = "user") -> str:
    """Create a JWT access token."""
    if not is_secret_key_safe(settings.secret_key):
        raise ValueError("SECRET_KEY not configured")

    expire = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS)
    to_encode = {
        "sub": str(user_id),
        "username": username,
        "exp": expire,
    }
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)


def verify_token(token: str) -> dict | None:
    """Verify and decode a JWT token."""
    if not is_secret_key_safe(settings.secret_key):
        logger.warning("SECRET_KEY not configured, token verification skipped")
        return None

    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {e}")
        return None


def get_current_user_id(token: str) -> int | None:
    """Extract user ID from token."""
    payload = verify_token(token)
    if payload:
        return int(payload.get("sub", 0))
    return None

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> int | None:
    """Dependency to get current user from Bearer token.

    Never bypasses authentication. If first-time setup has not been completed
    (no AUTH_PASSWORD / no SECRET_KEY) every protected endpoint returns 401
    with a "setup required" hint so the client can drive the setup flow via
    `/config/setup` (which is intentionally unauthenticated). See issue #323.
    """
    if not is_setup_complete():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Setup required: complete first-time setup via /config/setup before using the API.",
        )

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = get_current_user_id(credentials.credentials)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user_id
