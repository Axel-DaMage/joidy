from datetime import date, datetime

from database import Base
from sqlalchemy import Date, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship


class PlanningAssignment(Base):
    __tablename__ = "planning_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    goal_id: Mapped[int] = mapped_column(Integer, ForeignKey("goals.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=None)

    goal = relationship("Goal")
