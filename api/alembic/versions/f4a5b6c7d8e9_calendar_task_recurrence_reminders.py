"""calendar_tasks: recurrence + reminder_minutes

Revision ID: f4a5b6c7d8e9
Revises: d2e3f4a5b6c7
Create Date: 2026-11-24 00:00:00.000000

Recurring tasks + reminders (#1238, epic phase 3): `recurrence` drives
spawn-on-done (NONE/DAILY/WEEKLY/MONTHLY), `reminder_minutes` is the
minutes-before-start offset the frontend fires at (NULL = no reminder).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM

# revision identifiers, used by Alembic.
revision: str = "f4a5b6c7d8e9"
down_revision: str | None = "d2e3f4a5b6c7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RECURRENCE_VALUES = ["NONE", "DAILY", "WEEKLY", "MONTHLY"]


def upgrade() -> None:
    recurrence_enum = ENUM(
        *RECURRENCE_VALUES,
        name="calendar_task_recurrence",
        create_type=False,
    )
    recurrence_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "calendar_tasks",
        sa.Column("recurrence", recurrence_enum, nullable=False, server_default="NONE"),
    )
    op.add_column(
        "calendar_tasks",
        sa.Column("reminder_minutes", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("calendar_tasks", "reminder_minutes")
    op.drop_column("calendar_tasks", "recurrence")
    sa.Enum(name="calendar_task_recurrence").drop(op.get_bind(), checkfirst=True)
