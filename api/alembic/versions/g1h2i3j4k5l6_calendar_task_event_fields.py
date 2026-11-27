"""calendar_tasks: event-editor fields (description/location/attendees/note_id)

Revision ID: g1h2i3j4k5l6
Revises: c6d7e8f9a0b1
Create Date: 2026-11-25 00:00:00.000000

Planning suite (#1658): the calendar event editor covers Google-parity
fields. ``description`` and ``location`` are free text mirrored to Google on
publish; ``attendees`` stores a comma-separated e-mail list translated into
Google ``attendees`` objects on write-back; ``note_id`` links a vault note
created from the event (quick-capture backlink).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "g1h2i3j4k5l6"
down_revision: str | None = "c6d7e8f9a0b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("calendar_tasks", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("calendar_tasks", sa.Column("location", sa.String(500), nullable=True))
    op.add_column("calendar_tasks", sa.Column("attendees", sa.Text(), nullable=True))
    op.add_column(
        "calendar_tasks",
        sa.Column("note_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_calendar_tasks_note_id",
        "calendar_tasks",
        "notes",
        ["note_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_calendar_tasks_note_id", "calendar_tasks", ["note_id"])


def downgrade() -> None:
    op.drop_index("ix_calendar_tasks_note_id", table_name="calendar_tasks")
    op.drop_constraint("fk_calendar_tasks_note_id", "calendar_tasks", type_="foreignkey")
    op.drop_column("calendar_tasks", "note_id")
    op.drop_column("calendar_tasks", "attendees")
    op.drop_column("calendar_tasks", "location")
    op.drop_column("calendar_tasks", "description")
