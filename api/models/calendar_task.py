from datetime import date, datetime
from enum import Enum as PyEnum

from database import Base
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship


class CalendarTaskPriority(str, PyEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class CalendarTaskSource(str, PyEnum):
    JOIDY = "JOIDY"
    GOOGLE = "GOOGLE"


class CalendarTaskRecurrence(str, PyEnum):
    NONE = "NONE"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"


class CalendarTask(Base):
    """Internal joidy calendar task: schedulable unit with time, priority and done state.

    Lives alongside the read-only Google Calendar cache (google_calendar_events).
    A task may optionally link to a goal and mirror itself into a Google Calendar
    event (source=GOOGLE + google_event_id) once write-back exists (#1233).
    A NULL date means the task sits in the unscheduled queue ("sin planificar",
    #1234) until it is dragged onto a day.
    """

    __tablename__ = "calendar_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    start_time: Mapped[datetime | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(Time, nullable=True)
    priority: Mapped[CalendarTaskPriority] = mapped_column(
        Enum(CalendarTaskPriority, name="calendar_task_priority"),
        nullable=False,
        default=CalendarTaskPriority.MEDIUM,
    )
    done: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    done_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    goal_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("goals.id", ondelete="SET NULL"), nullable=True)
    source: Mapped[CalendarTaskSource] = mapped_column(
        Enum(CalendarTaskSource, name="calendar_task_source"),
        nullable=False,
        default=CalendarTaskSource.JOIDY,
    )
    google_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Recurring tasks (#1238): completing a scheduled non-goal task spawns the
    # next occurrence. NONE disables spawning entirely.
    recurrence: Mapped[CalendarTaskRecurrence] = mapped_column(
        Enum(CalendarTaskRecurrence, name="calendar_task_recurrence"),
        nullable=False,
        default=CalendarTaskRecurrence.NONE,
        server_default="NONE",
    )
    # Minutes before start_time to remind at; NULL = no reminder (frontend fires it).
    reminder_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Full event-editor fields (#1658): free-form description and location,
    # comma-separated attendee e-mails (mirrored to Google on publish), and
    # an optional vault note created from the event (quick-capture backlink).
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(500), nullable=True)
    attendees: Mapped[str | None] = mapped_column(Text, nullable=True)
    note_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("notes.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    goal = relationship("Goal")
    note = relationship("Note")

    __table_args__ = (
        Index("ix_calendar_tasks_goal_id", "goal_id"),
        Index("ix_calendar_tasks_date_priority", "date", "priority"),
        # execution_queue filters on done and orders by start_time/created_at
        # (#1524).
        Index("ix_calendar_tasks_done", "done"),
        Index("ix_calendar_tasks_start_time", "start_time"),
        Index("ix_calendar_tasks_created_at", "created_at"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<CalendarTask {self.id}:{self.title[:30]}>"
