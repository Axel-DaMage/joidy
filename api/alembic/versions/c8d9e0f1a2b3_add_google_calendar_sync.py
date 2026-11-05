"""add google calendar sync tables

Revision ID: c8d9e0f1a2b3
Revises: 9f3e2d1c4b5a
Create Date: 2026-11-05 10:00:00.000000

Local cache for Google Calendar events (#1134): google_calendar_events
stores expanded event instances upserted by (user_id, calendar_id,
google_id); google_calendar_sync_state keeps the per-calendar
nextSyncToken for incremental syncs.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c8d9e0f1a2b3"
down_revision: str | None = "9f3e2d1c4b5a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "google_calendar_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("calendar_id", sa.String(length=255), nullable=False),
        sa.Column("google_id", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="confirmed"),
        sa.Column("all_day", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("html_link", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "calendar_id", "google_id", name="uq_gcal_event_user_cal_gid"),
    )
    op.create_index(op.f("ix_google_calendar_events_id"), "google_calendar_events", ["id"], unique=False)
    op.create_index(op.f("ix_google_calendar_events_user_id"), "google_calendar_events", ["user_id"], unique=False)
    op.create_index("ix_gcal_events_user_start", "google_calendar_events", ["user_id", "start_at"], unique=False)
    op.create_index(
        "ix_gcal_events_user_cal_start", "google_calendar_events", ["user_id", "calendar_id", "start_at"], unique=False
    )

    op.create_table(
        "google_calendar_sync_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("calendar_id", sa.String(length=255), nullable=False),
        sa.Column("sync_token", sa.Text(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "calendar_id", name="uq_gcal_sync_user_cal"),
    )
    op.create_index(op.f("ix_google_calendar_sync_state_id"), "google_calendar_sync_state", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_google_calendar_sync_state_id"), table_name="google_calendar_sync_state")
    op.drop_table("google_calendar_sync_state")
    op.drop_index("ix_gcal_events_user_cal_start", table_name="google_calendar_events")
    op.drop_index("ix_gcal_events_user_start", table_name="google_calendar_events")
    op.drop_index(op.f("ix_google_calendar_events_user_id"), table_name="google_calendar_events")
    op.drop_index(op.f("ix_google_calendar_events_id"), table_name="google_calendar_events")
    op.drop_table("google_calendar_events")
