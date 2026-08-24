"""add usage_events table for internal usage tracking

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-08-03 10:00:00.000000

Analytics dashboard + internal usage tracking (#251, #250). Records
lightweight usage events (page_view, feature_use, session_start,
session_end) only while the web app is in the foreground. The
``event_data`` column is a JSON blob holding context for the event.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "usage_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("event_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_usage_events_id"), "usage_events", ["id"], unique=False)
    op.create_index(op.f("ix_usage_events_user_id"), "usage_events", ["user_id"], unique=False)
    op.create_index("ix_usage_events_user_created", "usage_events", ["user_id", "created_at"], unique=False)
    op.create_index("ix_usage_events_type", "usage_events", ["event_type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_usage_events_type", table_name="usage_events")
    op.drop_index("ix_usage_events_user_created", table_name="usage_events")
    op.drop_index(op.f("ix_usage_events_user_id"), table_name="usage_events")
    op.drop_index(op.f("ix_usage_events_id"), table_name="usage_events")
    op.drop_table("usage_events")
