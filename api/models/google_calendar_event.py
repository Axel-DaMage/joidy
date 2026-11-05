from datetime import datetime

from database import Base
from sqlalchemy import (
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


class GoogleCalendarEvent(Base):
    """Cached Google Calendar event (expanded instances, singleEvents=true).

    Upserted by ``(user_id, calendar_id, google_id)`` during sync so repeated
    incremental syncs (syncToken) converge into one local view. Cancelled
    events are removed instead of upserted.
    """

    __tablename__ = "google_calendar_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    calendar_id: Mapped[str] = mapped_column(String(255), nullable=False)
    google_id: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="confirmed")
    all_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    html_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "calendar_id", "google_id", name="uq_gcal_event_user_cal_gid"),
        Index("ix_gcal_events_user_start", "user_id", "start_at"),
        Index("ix_gcal_events_user_cal_start", "user_id", "calendar_id", "start_at"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<GoogleCalendarEvent {self.calendar_id}:{self.google_id}>"
