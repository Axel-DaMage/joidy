from datetime import datetime

from database import Base
from sqlalchemy import BigInteger, DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column


class TelegramEvent(Base):
    """Persisted log of every interaction received on /telegram/webhook (#1132).

    One row per incoming Telegram update (command or plain message). Used for
    auditing, webhook retry de-duplication (``update_id``) and debugging:
    ``status`` records how the update ended (``processed``, ``ignored``,
    ``unauthorized``, ``error``) and ``response`` stores the reply that was
    sent back to the chat.
    """

    __tablename__ = "telegram_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    update_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    command: Mapped[str] = mapped_column(String(32), default="")
    message_text: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="received")
    response: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_telegram_events_status_created", "status", "created_at"),
        Index("ix_telegram_events_command", "command"),
    )
