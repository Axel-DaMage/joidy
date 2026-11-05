from datetime import datetime

from database import Base
from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column


class GoogleCalendarSyncState(Base):
    """Per-calendar incremental sync state (Google Calendar syncToken).

    One row per synced calendar. ``sync_token`` is the ``nextSyncToken``
    returned by the last events.list call; when Google answers 410 GONE the
    token expired and the next sync falls back to a full re-sync.
    """

    __tablename__ = "google_calendar_sync_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    calendar_id: Mapped[str] = mapped_column(String(255), nullable=False)
    sync_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (UniqueConstraint("user_id", "calendar_id", name="uq_gcal_sync_user_cal"),)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<GoogleCalendarSyncState {self.calendar_id}>"
