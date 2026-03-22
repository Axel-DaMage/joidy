from datetime import date, datetime
from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import relationship

from database import Base


class PersonalStreak(Base):
    __tablename__ = "personal_streaks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    emoji = Column(String, default="🔥")
    description = Column(String, default="")
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
    created_at = Column(DateTime, default=func.now())

    streak = relationship("PersonalStreak", back_populates="checkins")

    __table_args__ = (UniqueConstraint("streak_id", "check_date", name="uq_streak_checkin_date"),)
