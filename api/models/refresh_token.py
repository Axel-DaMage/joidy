"""Server-side refresh-token registry for rotation + reuse detection (#1457)."""

from datetime import datetime

from database import Base
from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column


class RefreshToken(Base):
    """One row per minted refresh token, keyed by its JWT ``jti`` claim.

    ``POST /auth/login`` starts a token *family*; every ``POST /auth/refresh``
    consumes the presented ``jti`` and mints its successor inside the same
    family (``family_id`` is preserved across rotations). Presenting an
    already-consumed ``jti`` means the token was replayed — a racing client
    or a stolen credential — so the whole family is revoked (standard
    refresh-token-rotation reuse detection). Rows are deleted lazily once
    ``expires_at`` passes; until then a consumed ``jti`` must stay on record
    so its reuse can still be detected.

    Timestamps are naive UTC, matching the ``DateTime`` columns used across
    the rest of the schema.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    jti: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    family_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(150), default="", nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
