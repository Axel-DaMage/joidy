"""
Authentication endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from config import settings
from services.auth_service import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=LoginResponse)
def login(username: str = "user", password: str = ""):
    """Simple login endpoint.

    For a personal app, we use a simple single-user auth.
    The password should be configured via AUTH_PASSWORD in .env.
    """
    if not settings.secret_key:
        raise HTTPException(status_code=500, detail="Server not configured for auth")

    # Simple single-user password check
    expected_password = settings.auth_password or ""
    if expected_password and password != expected_password:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Create token for the single user (user_id=1)
    token = create_access_token(user_id=1, username=username)
    return LoginResponse(access_token=token)


@router.get("/status")
def auth_status():
    """Check if authentication is configured."""
    return {
        "enabled": bool(settings.secret_key),
        "has_password": bool(settings.auth_password),
    }