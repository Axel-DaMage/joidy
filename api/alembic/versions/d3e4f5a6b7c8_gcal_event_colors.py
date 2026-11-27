"""google_calendar: event colorId + calendar background color

Revision ID: d3e4f5a6b7c8
Revises: e7f8a9b0c1d2
Create Date: 2026-11-26 00:00:00.000000

Surface real Google Calendar colors in the UI: events carry their own
``colorId`` ("1".."11") and each synced calendar keeps its
``backgroundColor`` from the calendarList. The effective color is resolved
at read time — event colorId wins, calendar color is the fallback — so
calendar recolors propagate without re-syncing every event.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d3e4f5a6b7c8"
down_revision: str | None = "e7f8a9b0c1d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "google_calendar_events",
        sa.Column("color_id", sa.String(length=8), nullable=True),
    )
    op.add_column(
        "google_calendar_sync_state",
        sa.Column("background_color", sa.String(length=9), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("google_calendar_sync_state", "background_color")
    op.drop_column("google_calendar_events", "color_id")
