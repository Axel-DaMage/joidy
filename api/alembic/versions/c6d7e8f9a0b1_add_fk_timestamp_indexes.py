"""add missing indexes on FK/join and hot timestamp columns

Revision ID: c6d7e8f9a0b1
Revises: b4c5d6e7f8a9
Create Date: 2026-08-30 12:00:00.000000

PostgreSQL does not auto-create indexes on foreign keys. Several FK columns
used in WHERE/JOIN clauses and hot timestamp columns used in filters and
ORDER BYs were unindexed, causing sequential scans that grow with table
size (#1524):

- github_items.repo_id / goal_id / note_id: filtered at
  routers/integrations/github.py (``/db/items``) and joined on
  repo/goal/note deletes (CASCADE / SET NULL).
- github_events.repo_id: filtered by repo event feeds; created_at is
  filtered/ordered alone by analytics rollups.
- planning_assignments.goal_id: joined on goal delete (CASCADE).
- xp_events.created_at: range-filtered and ordered by stats/analytics
  and get_recent on one of the fastest-growing tables.
- goals.completed_at: filtered by get_completed_since.
- calendar_tasks.done / start_time / created_at: filtered and ordered by
  the execution-queue endpoint.

Skipped from the issue after verification:

- usage_events.created_at is always queried together with user_id and is
  already covered by ix_usage_events_user_created.
- notes.is_embedded is written but never filtered; the embedding retry
  path uses embedding_failures (already indexed).
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c6d7e8f9a0b1"
down_revision: str | None = "b4c5d6e7f8a9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_github_items_repo_id", "github_items", ["repo_id"], unique=False)
    op.create_index("ix_github_items_goal_id", "github_items", ["goal_id"], unique=False)
    op.create_index("ix_github_items_note_id", "github_items", ["note_id"], unique=False)
    op.create_index("ix_github_events_repo_id", "github_events", ["repo_id"], unique=False)
    op.create_index("ix_github_events_created_at", "github_events", ["created_at"], unique=False)
    op.create_index("ix_planning_assignments_goal_id", "planning_assignments", ["goal_id"], unique=False)
    op.create_index("ix_xp_events_created_at", "xp_events", ["created_at"], unique=False)
    op.create_index("ix_goals_completed_at", "goals", ["completed_at"], unique=False)
    op.create_index("ix_calendar_tasks_done", "calendar_tasks", ["done"], unique=False)
    op.create_index("ix_calendar_tasks_start_time", "calendar_tasks", ["start_time"], unique=False)
    op.create_index("ix_calendar_tasks_created_at", "calendar_tasks", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_calendar_tasks_created_at", table_name="calendar_tasks")
    op.drop_index("ix_calendar_tasks_start_time", table_name="calendar_tasks")
    op.drop_index("ix_calendar_tasks_done", table_name="calendar_tasks")
    op.drop_index("ix_goals_completed_at", table_name="goals")
    op.drop_index("ix_xp_events_created_at", table_name="xp_events")
    op.drop_index("ix_planning_assignments_goal_id", table_name="planning_assignments")
    op.drop_index("ix_github_events_created_at", table_name="github_events")
    op.drop_index("ix_github_events_repo_id", table_name="github_events")
    op.drop_index("ix_github_items_note_id", table_name="github_items")
    op.drop_index("ix_github_items_goal_id", table_name="github_items")
    op.drop_index("ix_github_items_repo_id", table_name="github_items")
