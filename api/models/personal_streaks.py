from datetime import date, datetime
from sqlalchemy import Column, Integer, String, Date, DateTime, Boolean, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import relationship

from database import Base


class PersonalStreak(Base):
    __tablename__ = "personal_streaks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    emoji = Column(String, default="🔥")
    icon = Column(String, default="")                 # Lucide icon name (alternative to emoji)
    description = Column(String, default="")
    color = Column(String, default="")
    theme = Column(String, default="solid")            # 'solid' | 'gradient' | 'glow' | 'minimal'
    category = Column(String, default="general")       # general, salud, estudio, fitness, creatividad, habito, trabajo
    start_date = Column(Date, nullable=True)
    target_date = Column(Date, nullable=True)          # Optional goal date
    offset = Column(Integer, default=0)                # For migrating streaks from other apps
    frequency = Column(String, default="daily")        # 'daily' | 'every_n'
    frequency_days = Column(Integer, default=1)        # Every N days (1 = daily)
    is_archived = Column(Boolean, default=False)
    best_streak = Column(Integer, default=0)           # Historical record
    total_checkins = Column(Integer, default=0)        # Accumulated check-in count
    freeze_count = Column(Integer, default=0)          # Available shields
    freeze_used = Column(Integer, default=0)           # Shields used
    created_at = Column(DateTime, default=func.now())

    checkins = relationship(
        "StreakCheckIn",
        back_populates="streak",
        cascade="all, delete-orphan",
        order_by="StreakCheckIn.check_date",
    )


class StreakCheckIn(Base):
    __tablename__ = "streak_checkins"

    id = Column(Integer, primary_key=True, autoincrement=True)
    streak_id = Column(Integer, ForeignKey("personal_streaks.id", ondelete="CASCADE"), nullable=False)
    check_date = Column(Date, nullable=False)
    note = Column(String, default="")
    mood = Column(Integer, nullable=True)  # 1-5
    created_at = Column(DateTime, default=func.now())

    streak = relationship("PersonalStreak", back_populates="checkins")

    __table_args__ = (UniqueConstraint("streak_id", "check_date", name="uq_streak_checkin_date"),)
