"""Google OAuth token storage and refresh service.

Stores the refresh token encrypted with Fernet (using the app SECRET_KEY),
and provides helpers to get a valid access token (auto-refreshing when
expired).
"""

import base64
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from config import settings
from cryptography.fernet import Fernet, InvalidToken
from models.google_token import GoogleToken
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


def _get_fernet() -> Fernet:
    """Derive a Fernet key from the app's SECRET_KEY."""
    key = hashlib.sha256(settings.secret_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_token(token: str) -> str:
    return _get_fernet().encrypt(token.encode()).decode()


def decrypt_token(encrypted: str) -> str | None:
    try:
        return _get_fernet().decrypt(encrypted.encode()).decode()
    except (InvalidToken, Exception):
        logger.error("[google] Failed to decrypt token")
        return None


def store_tokens(
    db: Session,
    *,
    access_token: str,
    refresh_token: str | None,
    expires_in: int,
    token_type: str = "Bearer",
    scope: str | None = None,
) -> GoogleToken:
    """Store or update Google OAuth tokens in the database."""
    row = db.query(GoogleToken).filter(GoogleToken.user_id == 1).first()
    if not row:
        row = GoogleToken(user_id=1)
        db.add(row)

    row.access_token = access_token
    if refresh_token:
        row.refresh_token_encrypted = encrypt_token(refresh_token)
    row.token_type = token_type
    row.expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    row.scope = scope
    db.commit()
    db.refresh(row)
    return row


def get_stored_token(db: Session) -> GoogleToken | None:
    return db.query(GoogleToken).filter(GoogleToken.user_id == 1).first()


def is_connected(db: Session) -> bool:
    row = get_stored_token(db)
    if not row:
        return False
    if not row.refresh_token_encrypted:
        return False
    return decrypt_token(row.refresh_token_encrypted) is not None


def clear_tokens(db: Session) -> None:
    row = get_stored_token(db)
    if row:
        db.delete(row)
        db.commit()


async def get_valid_access_token(db: Session) -> str | None:
    """Return a valid access token, refreshing if necessary.

    Returns None if not connected or refresh fails.
    """
    row = get_stored_token(db)
    if not row or not row.refresh_token_encrypted:
        return None

    # If access token is still valid (with 60s buffer), use it
    if row.access_token and row.expires_at:
        now = datetime.now(timezone.utc)
        expires_at = row.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if now < expires_at - timedelta(seconds=60):
            return row.access_token

    # Need to refresh
    refresh_token = decrypt_token(row.refresh_token_encrypted)
    if not refresh_token:
        return None

    if not settings.google_client_id or not settings.google_client_secret:
        logger.warning("[google] Cannot refresh: client credentials not configured")
        return None

    payload = {
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(GOOGLE_TOKEN_URL, data=payload)
            r.raise_for_status()
            data: dict[str, Any] = r.json()
    except Exception as e:
        logger.error("[google] Token refresh failed: %s", e)
        return None

    new_access = data.get("access_token", "")
    expires_in = data.get("expires_in", 3600)

    row.access_token = new_access
    row.expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    db.commit()

    return new_access
