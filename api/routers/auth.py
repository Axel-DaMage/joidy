"""
Authentication endpoints.
"""

from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from services.auth_service import (
    TOKEN_TYPE_REFRESH,
    _effective_auth_password,
    _effective_secret_key,
    create_access_token,
    verify_password,
    verify_token,
)
from services.refresh_token_service import (
    RefreshTokenError,
    issue_refresh_token,
    purge_expired_tokens,
    revoke_family_by_jti,
    rotate_refresh_token,
)
from sqlalchemy.orm import Session

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    password: str = ""
    username: str = "user"


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105 — OAuth2 token-type label, not a password


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str = ""


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """Simple login endpoint.

    For a personal app, we use a simple single-user auth.
    The password should be configured via AUTH_PASSWORD in .env.

    Credentials are read from the JSON request body, not query parameters,
    to avoid credentials leaking into URLs, proxy access logs, and browser
    history (#647).

    Returns a short-lived access token plus a longer-lived refresh token so
    sessions can be renewed without re-asking the password (#1285). The
    refresh token's ``jti`` is registered server-side — it starts the token
    family later rotations continue (#1457).
    """
    if not _effective_secret_key():
        raise HTTPException(status_code=500, detail="Server not configured for auth")

    expected_password = _effective_auth_password()
    if expected_password and not verify_password(body.password, expected_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Lazy sweep of expired refresh-token rows — keeps the registry bounded
    # without a background job. Consumed-but-unexpired rows stay: their
    # consumed_at marker is what makes replay detection work.
    purge_expired_tokens(db)

    # Create tokens for the single user (user_id=1)
    return TokenResponse(
        access_token=create_access_token(user_id=1, username=body.username),
        refresh_token=issue_refresh_token(db, user_id=1, username=body.username),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    """Exchange a valid refresh token for a new token pair (#1285, #1457).

    The refresh token is validated for signature, expiry, issuer, audience
    and ``typ=refresh`` — access tokens or foreign-issuer credentials are
    rejected. The presented ``jti`` is then consumed atomically and a
    successor is minted in the same family (rotation). Re-presenting a
    consumed ``jti`` is treated as token theft: the whole family is revoked
    and the request fails closed with 401. Unknown, revoked or expired
    ``jti`` values are rejected outright.
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
    jti = payload.get("jti", "")
    if not user_id or not jti:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    try:
        new_refresh_token = rotate_refresh_token(db, jti)
    except RefreshTokenError:
        # Same 401 for invalid and reuse paths — the reuse signal is logged
        # server-side; leaking which case fired would be an oracle.
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token") from None

    return TokenResponse(
        access_token=create_access_token(user_id=user_id, username=payload.get("username", "user")),
        refresh_token=new_refresh_token,
    )


@router.post("/logout")
def logout(body: LogoutRequest, db: Session = Depends(get_db)):
    """Invalidate the active refresh-token family (#1457).

    Accepts the session's current refresh token and revokes its whole family,
    so every rotated descendant dies with it. The endpoint is unauthenticated
    — the refresh token presented in the body is itself the credential being
    revoked — and idempotent: invalid, expired or already-revoked tokens all
    return the same response so the endpoint can't be used as a validity
    oracle.
    """
    if _effective_secret_key() and body.refresh_token:
        payload = verify_token(body.refresh_token, expected_type=TOKEN_TYPE_REFRESH)
        if payload and payload.get("jti"):
            revoke_family_by_jti(db, payload["jti"])
    return {"status": "ok"}


@router.get("/status")
def auth_status():
    """Check if authentication is configured.

    Only exposes whether auth is enabled — never whether a password is set,
    to avoid giving attackers a reconnaissance signal (#647).
    """
    return {
        "enabled": bool(_effective_secret_key()),
    }
