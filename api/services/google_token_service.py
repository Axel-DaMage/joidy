"""Google OAuth token storage and refresh service.

Both OAuth tokens are encrypted at rest with Fernet (app SECRET_KEY) via the
shared ``encryption`` module: the refresh token through explicit
``encrypt_token`` calls, and the access token transparently through the
``EncryptedText`` column on ``GoogleToken`` (#1286). Provides helpers to get
a valid access token (auto-refreshing when expired).
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from config import settings
from encryption import decrypt_str, encrypt_str
from models.google_token import GoogleToken
from services.http_client import http_client
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105 — OAuth endpoint URL, not a password


def encrypt_token(token: str) -> str:
    return encrypt_str(token)


def decrypt_token(encrypted: str) -> str | None:
    return decrypt_str(encrypted)


def store_tokens(
    db: Session,
    *,
    access_token: str,
    refresh_token: str | None,
    expires_in: int,
    token_type: str = "Bearer",  # noqa: S107 — OAuth2 token-type label default, not a password
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
    row.expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)
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


async def refresh_access_token(refresh_token: str) -> dict[str, Any] | None:
    """Exchange a Google OAuth refresh token for a fresh access token.

    Returns the provider JSON (``access_token``, ``expires_in``, …) or None
    on failure. Shared by the single ``google_tokens`` row and per-account
    Gmail credentials on ``email_accounts`` (#1659).
    """
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
        async with http_client(timeout=30.0) as client:
            r = await client.post(GOOGLE_TOKEN_URL, data=payload)
            r.raise_for_status()
            return r.json()
    except Exception as e:
        logger.error("[google] Token refresh failed: %s", e)
        return None


async def get_valid_access_token(db: Session) -> str | None:
    """Return a valid access token, refreshing if necessary.

    Returns None if not connected or refresh fails.
    """
    row = get_stored_token(db)
    if not row or not row.refresh_token_encrypted:
        return None

    # If access token is still valid (with 60s buffer), use it
    if row.access_token and row.expires_at:
        now = datetime.now(UTC)
        expires_at = row.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if now < expires_at - timedelta(seconds=60):
            return row.access_token

    # Need to refresh
    refresh_token = decrypt_token(row.refresh_token_encrypted)
    if not refresh_token:
        return None

    data = await refresh_access_token(refresh_token)
    if not data:
        return None

    new_access: str = data.get("access_token", "")
    expires_in = data.get("expires_in", 3600)

    row.access_token = new_access
    row.expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)
    db.commit()

    return new_access
