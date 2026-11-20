"""
Authentication endpoints.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.auth_service import (
    TOKEN_TYPE_REFRESH,
    _effective_auth_password,
    _effective_secret_key,
    create_access_token,
    create_refresh_token,
    verify_password,
    verify_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    password: str = ""
    username: str = "user"


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest):
    """Simple login endpoint.

    For a personal app, we use a simple single-user auth.
    The password should be configured via AUTH_PASSWORD in .env.

    Credentials are read from the JSON request body, not query parameters,
    to avoid credentials leaking into URLs, proxy access logs, and browser
    history (#647).

    Returns a short-lived access token plus a longer-lived refresh token so
    sessions can be renewed without re-asking the password (#1285).
    """
    if not _effective_secret_key():
        raise HTTPException(status_code=500, detail="Server not configured for auth")

    expected_password = _effective_auth_password()
    if expected_password and not verify_password(body.password, expected_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Create tokens for the single user (user_id=1)
    return TokenResponse(
        access_token=create_access_token(user_id=1, username=body.username),
        refresh_token=create_refresh_token(user_id=1, username=body.username),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest):
    """Exchange a valid refresh token for a new token pair (#1285).

    The refresh token is validated for signature, expiry, issuer, audience
    and ``typ=refresh`` — access tokens or foreign-issuer credentials are
    rejected. A fresh refresh token is returned on every call (rotation), so
    the sliding session window only persists while the app is in use.
    """
    if not _effective_secret_key():
        raise HTTPException(status_code=500, detail="Server not configured for auth")

    payload = verify_token(body.refresh_token, expected_type=TOKEN_TYPE_REFRESH)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    try:
        user_id = int(payload.get("sub", "0"))
    except ValueError:
        user_id = 0
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    return TokenResponse(
        access_token=create_access_token(user_id=user_id, username=payload.get("username", "user")),
        refresh_token=create_refresh_token(user_id=user_id, username=payload.get("username", "user")),
    )


@router.get("/status")
def auth_status():
    """Check if authentication is configured.

    Only exposes whether auth is enabled — never whether a password is set,
    to avoid giving attackers a reconnaissance signal (#647).
    """
    return {
        "enabled": bool(_effective_secret_key()),
    }
