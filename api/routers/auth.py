"""
Authentication endpoints.
"""

from config import settings
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.auth_service import create_access_token, verify_password, hash_password

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    password: str = ""
    username: str = "user"


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest):
    """Simple login endpoint.

    For a personal app, we use a simple single-user auth.
    The password should be configured via AUTH_PASSWORD in .env.

    Credentials are read from the JSON request body, not query parameters,
    to avoid credentials leaking into URLs, proxy access logs, and browser
    history (#647).
    """
    if not settings.secret_key:
        raise HTTPException(status_code=500, detail="Server not configured for auth")

    expected_password = settings.auth_password or ""
    if expected_password and not verify_password(body.password, expected_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Create token for the single user (user_id=1)
    token = create_access_token(user_id=1, username=body.username)
    return LoginResponse(access_token=token)


@router.get("/status")
def auth_status():
    """Check if authentication is configured.

    Only exposes whether auth is enabled — never whether a password is set,
    to avoid giving attackers a reconnaissance signal (#647).
    """
    return {
        "enabled": bool(settings.secret_key),
    }
