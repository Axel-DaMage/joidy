from datetime import datetime

from database import Base
from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column


class Achievement(Base):
    """Achievement unlocked by a user — idempotent per (user_id, achievement_key)."""

    __tablename__ = "achievements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    achievement_key: Mapped[str] = mapped_column(String(100), nullable=False)
    unlocked_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True, default="{}")

    __table_args__ = (UniqueConstraint("user_id", "achievement_key", name="uq_achievements_user_key"),)
