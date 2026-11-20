from datetime import datetime

from database import Base
from encryption import EncryptedText
from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column


class IntegrationToken(Base):
    """Provider-agnostic OAuth token storage for external integrations (#44).

    One row per provider (``provider`` is unique): Strava today, Spotify next
    (#45) — the same table serves every OAuth integration so adding a
    provider never needs another migration.

    Both tokens are encrypted at rest with Fernet (app SECRET_KEY): the
    access token transparently via the ``EncryptedText`` column, the refresh
    token via explicit ``encrypt_str`` calls in
    ``services.integration_token_service`` (same scheme as
    ``GoogleToken`` / #1286). Reads transparently return plaintext.

    ``account_id`` optionally stores the provider-side user identifier
    (Strava athlete id, Spotify user id) for webhook owner checks and
    status display without an extra API call.
    """

    __tablename__ = "integration_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    provider: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    access_token: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_type: Mapped[str] = mapped_column(String, default="Bearer", nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    account_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
