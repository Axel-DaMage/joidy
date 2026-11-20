from datetime import datetime

from database import Base
from sqlalchemy import DateTime, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON


class ChatSession(Base):
    """AI chat conversation persisted per user (#1131).

    ``messages`` is a JSON list of ``{"role", "content", "ts"}`` turns so the
    /ai page can restore the conversation across reloads and devices instead
    of relying on sessionStorage. ``title`` is derived from the first user
    message for future multi-session listings.
    """

    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    messages: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_chat_sessions_user_updated", "user_id", "updated_at"),)
