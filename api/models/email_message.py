from datetime import datetime

from database import Base
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column


class EmailMessage(Base):
    """Unified inbox entry imported from external mail providers (e.g. Gmail via n8n).

    Upserted by ``(user_id, account, gmail_id)`` so repeated sync runs from
    multiple accounts converge into one inbox view.
    """

    __tablename__ = "email_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    account: Mapped[str] = mapped_column(String(255), nullable=False)
    gmail_id: Mapped[str] = mapped_column(String(64), nullable=False)
    thread_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    sender: Mapped[str | None] = mapped_column(String(320), nullable=True)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    unread: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    important: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    importance_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    labels: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "account", "gmail_id", name="uq_email_user_account_gmail"),
        Index("ix_email_messages_user_unread", "user_id", "unread"),
        Index("ix_email_messages_user_important", "user_id", "important"),
        Index("ix_email_messages_received_at", "received_at"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        account = getattr(self, "account", "?")
        return f"<EmailMessage {account}:{self.gmail_id}>"
