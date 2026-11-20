"""calendar_tasks.date nullable

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-11-20 00:00:00.000000

Unscheduled queue (#1234): a calendar task may exist without a date and
wait in the "sin planificar" tray until it is dragged onto a day.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d2e3f4a5b6c7"
down_revision: str | None = "c1d2e3f4a5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("calendar_tasks", "date", existing_type=sa.Date(), nullable=True)


def downgrade() -> None:
    # WARNING — data loss on downgrade (#1332): rows parked in the
    # unscheduled queue have no date to keep, so they are DELETEd outright
    # before restoring NOT NULL. Review them first if the data matters:
    #   SELECT * FROM calendar_tasks WHERE date IS NULL;
    op.execute("DELETE FROM calendar_tasks WHERE date IS NULL")
    op.alter_column("calendar_tasks", "date", existing_type=sa.Date(), nullable=False)
