from datetime import date, datetime

from database import Base
from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship


class PlanningAssignment(Base):
    __tablename__ = "planning_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    goal_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("goals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    # Google Calendar event this assignment was created from (goal-from-event
    # flow). Lets planning hide the raw event chip — the goal chip represents
    # it — instead of rendering the same item twice.
    source_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    goal = relationship("Goal")
