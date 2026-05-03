from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class GoalTemporality(str, PyEnum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    ANNUAL = "ANNUAL"


class GoalMeasurement(str, PyEnum):
    COUNT = "COUNT"
    BOOLEAN = "BOOLEAN"
    PERCENT = "PERCENT"


class GoalState(str, PyEnum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PAUSED = "PAUSED"
    CANCELLED = "CANCELLED"


class GoalFailConfig(str, PyEnum):
    STATIC = "STATIC"
    ROLLOVER = "ROLLOVER"
    SNOWBALL = "SNOWBALL"


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    
    temporality: Mapped[GoalTemporality] = mapped_column(Enum(GoalTemporality), default=GoalTemporality.DAILY)
    measurement_type: Mapped[GoalMeasurement] = mapped_column(Enum(GoalMeasurement), default=GoalMeasurement.COUNT)
    
    target_value: Mapped[float] = mapped_column(Float, default=1.0)
    current_value: Mapped[float] = mapped_column(Float, default=0.0)
    max_assignment_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    state: Mapped[GoalState] = mapped_column(Enum(GoalState), default=GoalState.ACTIVE)
    fail_config: Mapped[GoalFailConfig] = mapped_column(Enum(GoalFailConfig), default=GoalFailConfig.STATIC)
    fail_emoji: Mapped[str] = mapped_column(String(20), default="🔴")
    color: Mapped[str] = mapped_column(String(20), default="#c8a96e")
    theme: Mapped[str] = mapped_column(String(20), default="solid")
    
    note_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("notes.id"), nullable=True)
    tag_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("tags.id"), nullable=True)
    
    parent_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("goals.id"), nullable=True)
    
    pending_removal: Mapped[bool] = mapped_column(Boolean, default=False)
    
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    source_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    tag: Mapped["Tag | None"] = relationship("Tag")  # type: ignore
    note: Mapped["Note | None"] = relationship("Note")  # type: ignore

