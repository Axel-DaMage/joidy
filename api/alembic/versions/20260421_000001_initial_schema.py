"""initial schema

Revision ID: 20260421_000001
Revises:
Create Date: 2026-04-21 00:00:01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260421_000001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return inspector.has_table(table_name)


def _create_indexes_if_missing() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes_by_table = {
        table: {idx["name"] for idx in inspector.get_indexes(table)}
        for table in inspector.get_table_names()
    }

    desired = [
        ("ix_notes_id", "notes", ["id"], True),
        ("ix_notes_source_path", "notes", ["source_path"], False),
        ("ix_tags_id", "tags", ["id"], True),
        ("ix_xp_events_id", "xp_events", ["id"], True),
        ("ix_streak_records_id", "streak_records", ["id"], True),
        ("ix_goals_id", "goals", ["id"], True),
        ("ix_skills_id", "skills", ["id"], True),
    ]

    for idx_name, table_name, columns, unique in desired:
        existing = indexes_by_table.get(table_name, set())
        if table_name in indexes_by_table and idx_name not in existing:
            op.create_index(idx_name, table_name, columns, unique=unique)


def upgrade() -> None:
    if not _has_table("notes"):
        op.create_table(
            "notes",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("title", sa.String(length=500), nullable=False),
            sa.Column("content", sa.Text(), nullable=False, server_default=""),
            sa.Column("source", sa.String(length=50), nullable=False, server_default="joidy"),
            sa.Column("source_path", sa.String(length=1000), nullable=True),
            sa.Column("is_embedded", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )

    if not _has_table("tags"):
        op.create_table(
            "tags",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("parent_id", sa.Integer(), sa.ForeignKey("tags.id"), nullable=True),
            sa.Column("color", sa.String(length=20), nullable=False, server_default="#888888"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("name", name="uq_tags_name"),
        )

    if not _has_table("note_tags"):
        op.create_table(
            "note_tags",
            sa.Column("note_id", sa.Integer(), sa.ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True, nullable=False),
            sa.Column("tag_id", sa.Integer(), sa.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True, nullable=False),
            sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
            sa.Column("source", sa.String(length=20), nullable=False, server_default="manual"),
        )

    if not _has_table("note_links"):
        op.create_table(
            "note_links",
            sa.Column("source_note_id", sa.Integer(), sa.ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True, nullable=False),
            sa.Column("target_note_id", sa.Integer(), sa.ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True, nullable=False),
            sa.Column("context_text", sa.Text(), nullable=True),
        )

    if not _has_table("xp_events"):
        op.create_table(
            "xp_events",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("event_type", sa.String(length=100), nullable=False),
            sa.Column("xp", sa.Integer(), nullable=False),
            sa.Column("metadata_json", sa.String(length=500), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )

    if not _has_table("streak_records"):
        op.create_table(
            "streak_records",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("activity_date", sa.Date(), nullable=False),
            sa.Column("xp_earned", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("activity_date", name="uq_streak_records_activity_date"),
        )

    if not _has_table("user_stats"):
        op.create_table(
            "user_stats",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("total_xp", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("current_streak", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("longest_streak", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("plant_stage", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_activity_date", sa.Date(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )

    if not _has_table("goals"):
        op.create_table(
            "goals",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("title", sa.String(length=500), nullable=False),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("target_notes", sa.Integer(), nullable=False, server_default="5"),
            sa.Column("tag_id", sa.Integer(), sa.ForeignKey("tags.id"), nullable=True),
            sa.Column("is_completed", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )

    if not _has_table("skills"):
        op.create_table(
            "skills",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("tag_id", sa.Integer(), sa.ForeignKey("tags.id"), nullable=False),
            sa.Column("note_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("level", sa.String(length=20), nullable=False, server_default="locked"),
            sa.Column("xp", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("first_unlocked_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("tag_id", name="uq_skills_tag_id"),
        )

    if not _has_table("personal_streaks"):
        op.create_table(
            "personal_streaks",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("emoji", sa.String(), nullable=False, server_default="🔥"),
            sa.Column("icon", sa.String(), nullable=False, server_default=""),
            sa.Column("description", sa.String(), nullable=False, server_default=""),
            sa.Column("color", sa.String(), nullable=False, server_default=""),
            sa.Column("theme", sa.String(), nullable=False, server_default="solid"),
            sa.Column("category", sa.String(), nullable=False, server_default="general"),
            sa.Column("start_date", sa.Date(), nullable=True),
            sa.Column("target_date", sa.Date(), nullable=True),
            sa.Column("offset", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("frequency", sa.String(), nullable=False, server_default="daily"),
            sa.Column("frequency_days", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("best_streak", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_checkins", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("freeze_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("freeze_used", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )

    if not _has_table("streak_checkins"):
        op.create_table(
            "streak_checkins",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("streak_id", sa.Integer(), sa.ForeignKey("personal_streaks.id", ondelete="CASCADE"), nullable=False),
            sa.Column("check_date", sa.Date(), nullable=False),
            sa.Column("note", sa.String(), nullable=False, server_default=""),
            sa.Column("mood", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("streak_id", "check_date", name="uq_streak_checkin_date"),
        )

    if not _has_table("note_embeddings"):
        op.create_table(
            "note_embeddings",
            sa.Column("note_id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("embedding", sa.LargeBinary(), nullable=False),
        )

    _create_indexes_if_missing()


def downgrade() -> None:
    op.drop_table("note_embeddings")
    op.drop_table("streak_checkins")
    op.drop_table("personal_streaks")
    op.drop_table("skills")
    op.drop_table("goals")
    op.drop_table("user_stats")
    op.drop_table("streak_records")
    op.drop_table("xp_events")
    op.drop_table("note_links")
    op.drop_table("note_tags")
    op.drop_table("tags")
    op.drop_table("notes")
