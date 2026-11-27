"""planning_assignments: source google event id

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-11-27 00:00:00.000000

Goal-from-event assignments remember which Google Calendar event they
were created from. Planning uses it to suppress the raw event chip on
that day — the goal chip already represents the same item — instead of
rendering a duplicate.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e4f5a6b7c8d9"
down_revision: str | None = "d3e4f5a6b7c8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "planning_assignments",
        sa.Column("source_event_id", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("planning_assignments", "source_event_id")
