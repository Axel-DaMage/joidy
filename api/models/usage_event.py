from datetime import datetime

from database import Base
from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON


class UsageEvent(Base):
    """Internal usage event — tracked only while the web app is open (#250).

    Records lightweight interactions (page views, feature use, session
    start/end) so the analytics dashboard can surface "most used features"
    and session statistics. ``event_data`` is a free-form JSON blob holding
    context relevant to the event type (e.g. ``{"path": "/notes"}``).
    """

    __tablename__ = "usage_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    event_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_usage_events_user_created", "user_id", "created_at"),
        Index("ix_usage_events_type", "event_type"),
    )
