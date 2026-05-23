"""
JWT Authentication Service.
"""

import jwt
import logging
from datetime import datetime, timedelta
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24 * 7  # 1 week


def create_access_token(user_id: int, username: str = "user") -> str:
    """Create a JWT access token."""
    if not settings.secret_key:
        raise ValueError("SECRET_KEY not configured")

    expire = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    to_encode = {
        "sub": str(user_id),
        "username": username,
        "exp": expire,
    }
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)


def verify_token(token: str) -> Optional[dict]:
    """Verify and decode a JWT token."""
    if not settings.secret_key:
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


def get_current_user_id(token: str) -> Optional[int]:
    """Extract user ID from token."""
    payload = verify_token(token)
    if payload:
        return int(payload.get("sub", 0))
    return None