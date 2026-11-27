"""Shared helpers for the OAuth token stores (#1530).

``google_token_service`` (single ``GoogleToken`` row) and
``integration_token_service`` (one ``IntegrationToken`` row per provider)
grew as parallel implementations of the same token lifecycle: Fernet
encrypt/decrypt wrappers, "access token still fresh" checks and expiry
normalization. Those helpers live here once — each service keeps only its
model-specific store/get/clear calls.
"""

from datetime import UTC, datetime, timedelta
from typing import Protocol

from encryption import decrypt_str, encrypt_str

# Refresh when the access token expires within this window — covers clock
# skew and in-flight requests that would otherwise 401 mid-call.
REFRESH_BUFFER_SECONDS = 60


class _RefreshTokenRow(Protocol):
    """Shape both token models share for the ``is_connected`` predicate."""

    refresh_token_encrypted: str | None


def encrypt_token(token: str) -> str:
    return encrypt_str(token)


def decrypt_token(encrypted: str) -> str | None:
    return decrypt_str(encrypted)


def resolve_expiry(expires_in: int | None, expires_at: datetime | None) -> datetime | None:
    """Normalize a token payload's expiry: an absolute ``expires_at`` wins
    (naive values read as UTC), else ``expires_in`` seconds from now, else
    ``None``."""
    if expires_at is not None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        return expires_at
    if expires_in is not None:
        return datetime.now(UTC) + timedelta(seconds=expires_in)
    return None


def access_token_fresh(
    access_token: str | None,
    expires_at: datetime | None,
    buffer_seconds: int = REFRESH_BUFFER_SECONDS,
) -> bool:
    """True when the stored access token is still usable beyond the refresh
    buffer — naive ``expires_at`` values are read as UTC."""
    if not access_token or not expires_at:
        return False
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return datetime.now(UTC) < expires_at - timedelta(seconds=buffer_seconds)


def has_usable_refresh_token(row: _RefreshTokenRow | None) -> bool:
    """``is_connected`` predicate shared by both stores: a row exists and its
    refresh token decrypts."""
    if row is None or not row.refresh_token_encrypted:
        return False
    return decrypt_token(row.refresh_token_encrypted) is not None
