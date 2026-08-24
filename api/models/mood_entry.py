from datetime import date, datetime

from database import Base
from sqlalchemy import Date, DateTime, Index, Integer, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column


class MoodEntry(Base):
    """Daily mood entry — one per user per day (1-5 scale)."""

    __tablename__ = "mood_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        # One mood entry per user per day.
        UniqueConstraint("user_id", "entry_date", name="uq_mood_entry_user_date"),
        # History queries filter/order by entry_date.
        Index("ix_mood_entries_entry_date", "entry_date"),
    )
