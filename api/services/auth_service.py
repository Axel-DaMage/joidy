"""
JWT Authentication Service.
"""

import logging
from datetime import datetime, timedelta, timezone

import jwt
from config import settings
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext

from services.env_file import get_persisted

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24 * 7  # 1 week

security = HTTPBearer(auto_error=False)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _effective_auth_password() -> str:
    """Return the current AUTH_PASSWORD, reading from disk on every call.

    Uvicorn runs with ``--workers 2``: ``settings.auth_password`` is loaded
    once at startup and ``POST /config/setup`` only updates the worker that
    served the request. Reading the persisted value here ensures every
    worker sees the same password immediately after setup, with no restart
    needed.
    """
    return get_persisted("AUTH_PASSWORD") or settings.auth_password or ""


def _effective_secret_key() -> str:
    """Return the current SECRET_KEY, reading from disk on every call.

    Same cross-worker rationale as ``_effective_auth_password``: tokens
    signed by the worker that ran setup must verify on its siblings.
    """
    return get_persisted("SECRET_KEY") or settings.secret_key or ""


def verify_password(plain: str, hashed_or_plain: str) -> bool:
    """Verify a password against a stored hash or plaintext.

    Supports bcrypt hashes (starting with $2b$) and plaintext for backward compat.
    """
    if hashed_or_plain.startswith("$2b$"):
        return pwd_context.verify(plain, hashed_or_plain)
    return plain == hashed_or_plain


def hash_password(plain: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(plain)


def create_access_token(user_id: int, username: str = "user") -> str:
    """Create a JWT access token."""
    secret = _effective_secret_key()
    if not secret:
        raise ValueError("SECRET_KEY not configured")

    expire = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS)
    to_encode = {
        "sub": str(user_id),
        "username": username,
        "exp": expire,
    }
    return jwt.encode(to_encode, secret, algorithm=ALGORITHM)


def verify_token(token: str) -> dict | None:
    """Verify and decode a JWT token."""
    secret = _effective_secret_key()
    if not secret:
        logger.warning("SECRET_KEY not configured, token verification skipped")
        return None

    try:
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
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

    In development without AUTH_PASSWORD, auth is bypassed for convenience.
    In production, auth is always required — missing AUTH_PASSWORD means
    no valid token can be issued, so all requests are rejected.
    """
    auth_password = _effective_auth_password()
    if not auth_password:
        if settings.app_env == "production":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication not configured. Set AUTH_PASSWORD in .env.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return 1
    
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
