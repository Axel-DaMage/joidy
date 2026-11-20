from datetime import datetime

from database import Base
from encryption import EncryptedText
from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column


class GoogleToken(Base):
    """Store Google OAuth tokens for the single-user app.

    Both tokens are encrypted at rest with Fernet (app SECRET_KEY) — the
    refresh token via explicit encrypt_token() calls, the access token via
    the EncryptedText column (#1286). Reads transparently return plaintext;
    rows written before encryption return the legacy plaintext as-is until
    the next write re-encrypts them.
    There is only one row (user_id=1) since Joidy is a single-user app.
    """

    __tablename__ = "google_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, default=1, unique=True)
    access_token: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_type: Mapped[str] = mapped_column(String, default="Bearer", nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
