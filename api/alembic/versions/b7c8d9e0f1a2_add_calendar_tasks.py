"""add calendar_tasks table

Revision ID: b7c8d9e0f1a2
Revises: c8d9e0f1a2b3
Create Date: 2026-11-17 12:00:00.000000

Internal joidy calendar tasks (#1230): schedulable units with time,
priority and done state, optionally linked to a goal and (later,
#1233) mirrored into a Google Calendar event.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM

# revision identifiers, used by Alembic.
revision: str = "b7c8d9e0f1a2"
down_revision: str | None = "c8d9e0f1a2b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PRIORITY_VALUES = ["LOW", "MEDIUM", "HIGH", "URGENT"]
SOURCE_VALUES = ["JOIDY", "GOOGLE"]


def upgrade() -> None:
    priority_enum = ENUM(
        *PRIORITY_VALUES,
        name="calendar_task_priority",
        create_type=True,
    )
    source_enum = ENUM(
        *SOURCE_VALUES,
        name="calendar_task_source",
        create_type=True,
    )
    op.create_table(
        "calendar_tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("end_time", sa.Time(), nullable=True),
        sa.Column("priority", priority_enum, nullable=False, server_default="MEDIUM"),
        sa.Column("done", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("done_at", sa.DateTime(), nullable=True),
        sa.Column("goal_id", sa.Integer(), sa.ForeignKey("goals.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source", source_enum, nullable=False, server_default="JOIDY"),
        sa.Column("google_event_id", sa.String(length=255), nullable=True),
        sa.Column("color", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_calendar_tasks_id"), "calendar_tasks", ["id"], unique=False)
    op.create_index(op.f("ix_calendar_tasks_date"), "calendar_tasks", ["date"], unique=False)
    op.create_index("ix_calendar_tasks_goal_id", "calendar_tasks", ["goal_id"], unique=False)
    op.create_index("ix_calendar_tasks_date_priority", "calendar_tasks", ["date", "priority"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_calendar_tasks_date_priority"), table_name="calendar_tasks")
    op.drop_index("ix_calendar_tasks_goal_id", table_name="calendar_tasks")
    op.drop_index(op.f("ix_calendar_tasks_date"), table_name="calendar_tasks")
    op.drop_index(op.f("ix_calendar_tasks_id"), table_name="calendar_tasks")
    op.drop_table("calendar_tasks")
    sa.Enum(name="calendar_task_source").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="calendar_task_priority").drop(op.get_bind(), checkfirst=True)
