"""Provider-agnostic OAuth token storage and refresh (#44).

One ``integration_tokens`` row per provider holds the access token
(encrypted at rest via ``EncryptedText``) and the refresh token (explicit
``encrypt_str`` — same Fernet scheme as ``google_token_service``/#1286).
Adding a provider (Spotify, #45) only takes a new ``provider`` key plus a
provider-specific refresh callable — no schema change.

``get_valid_access_token`` refreshes transparently near expiry. Providers
that rotate refresh tokens (Strava does on every refresh) must return the
new ``refresh_token`` from their refresher; it is persisted, replacing the
old one. A failed refresh returns ``None`` — callers map that to a
"reconnect required" error, never to a leaked/stale credential.
"""

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from encryption import decrypt_str, encrypt_str
from models.integration_token import IntegrationToken
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Refresh when the access token expires within this window — covers clock
# skew and in-flight requests that would otherwise 401 mid-call.
REFRESH_BUFFER_SECONDS = 60

# Well-known provider keys. The table is provider-agnostic; these constants
# keep call sites typo-proof.
PROVIDER_STRAVA = "strava"
PROVIDER_SPOTIFY = "spotify"  # reserved for #45

# A refresher takes the decrypted refresh token and returns a normalized
# token payload::
#
#     {
#         "access_token": str,          # required
#         "refresh_token": str | None,  # rotated refresh token, if any
#         "expires_in": int | None,     # seconds until expiry
#         "expires_at": datetime | None,# or an absolute expiry
#         "scope": str | None,
#         "account_id": str | None,     # provider-side user id, if known
#     }
Refresher = Callable[[str], Awaitable[dict[str, Any]]]


def encrypt_token(token: str) -> str:
    return encrypt_str(token)


def decrypt_token(encrypted: str) -> str | None:
    return decrypt_str(encrypted)


def _resolve_expiry(expires_in: int | None, expires_at: datetime | None) -> datetime | None:
    if expires_at is not None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        return expires_at
    if expires_in is not None:
        return datetime.now(UTC) + timedelta(seconds=expires_in)
    return None


def store_tokens(
    db: Session,
    provider: str,
    *,
    access_token: str,
    refresh_token: str | None = None,
    expires_in: int | None = None,
    expires_at: datetime | None = None,
    token_type: str = "Bearer",  # noqa: S107 — OAuth2 token-type label default, not a password
    scope: str | None = None,
    account_id: str | None = None,
) -> IntegrationToken:
    """Store or update the OAuth tokens for ``provider`` (one row per provider)."""
    row = get_stored_token(db, provider)
    if not row:
        row = IntegrationToken(provider=provider)
        db.add(row)

    row.access_token = access_token
    if refresh_token:
        row.refresh_token_encrypted = encrypt_token(refresh_token)
    row.token_type = token_type
    row.expires_at = _resolve_expiry(expires_in, expires_at)
    if scope is not None:
        row.scope = scope
    if account_id is not None:
        row.account_id = str(account_id)
    db.commit()
    db.refresh(row)
    return row


def get_stored_token(db: Session, provider: str) -> IntegrationToken | None:
    return db.query(IntegrationToken).filter(IntegrationToken.provider == provider).first()


def is_connected(db: Session, provider: str) -> bool:
    """True when a usable refresh token exists for ``provider``."""
    row = get_stored_token(db, provider)
    if not row or not row.refresh_token_encrypted:
        return False
    return decrypt_token(row.refresh_token_encrypted) is not None


def clear_tokens(db: Session, provider: str) -> None:
    row = get_stored_token(db, provider)
    if row:
        db.delete(row)
        db.commit()


async def get_valid_access_token(db: Session, provider: str, refresher: Refresher) -> str | None:
    """Return a valid access token for ``provider``, refreshing if needed.

    ``refresher`` is the provider-specific token-endpoint call (e.g.
    ``strava_service.refresh_tokens``). Returns ``None`` when the provider
    is not connected or the refresh fails — the caller should surface a
    reconnect error.
    """
    row = get_stored_token(db, provider)
    if not row or not row.refresh_token_encrypted:
        return None

    # Still-valid access token (with buffer) — no refresh needed.
    if row.access_token and row.expires_at:
        now = datetime.now(UTC)
        expires_at = row.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if now < expires_at - timedelta(seconds=REFRESH_BUFFER_SECONDS):
            return row.access_token

    refresh_token = decrypt_token(row.refresh_token_encrypted)
    if not refresh_token:
        return None

    try:
        data = await refresher(refresh_token)
    except Exception as e:  # noqa: BLE001 — any provider/transport failure means "not connected"
        logger.warning("[%s] Token refresh failed: %s", provider, e)
        return None

    new_access = data.get("access_token")
    if not isinstance(new_access, str) or not new_access:
        logger.warning("[%s] Token refresh returned no access_token", provider)
        return None

    # Persist everything the provider returned — including a rotated
    # refresh_token (Strava invalidates the old one on every refresh).
    row.access_token = new_access
    if data.get("refresh_token"):
        row.refresh_token_encrypted = encrypt_token(str(data["refresh_token"]))
    row.expires_at = _resolve_expiry(
        data.get("expires_in") if isinstance(data.get("expires_in"), int) else None,
        data.get("expires_at") if isinstance(data.get("expires_at"), datetime) else None,
    )
    if data.get("scope"):
        row.scope = str(data["scope"])
    if data.get("account_id") is not None:
        row.account_id = str(data["account_id"])
    db.commit()
    db.refresh(row)

    return new_access
