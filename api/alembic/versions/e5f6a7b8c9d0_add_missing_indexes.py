"""add missing indexes on FKs and frequently filtered/ordered columns

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-31 19:30:00.000000

PostgreSQL does not auto-create indexes on foreign keys (unlike MySQL/InnoDB),
and several columns used in WHERE/JOIN/ORDER BY clauses were unindexed,
causing full table scans as the dataset grows (#403).
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index('ix_goals_parent_id', 'goals', ['parent_id'], unique=False)
    op.create_index('ix_goals_note_id', 'goals', ['note_id'], unique=False)
    op.create_index('ix_goals_tag_id', 'goals', ['tag_id'], unique=False)
    op.create_index('ix_goals_state', 'goals', ['state'], unique=False)
    op.create_index('ix_notes_created_at', 'notes', ['created_at'], unique=False)
    op.create_index('ix_notes_updated_at', 'notes', ['updated_at'], unique=False)
    op.create_index('ix_note_links_target_note_id', 'note_links', ['target_note_id'], unique=False)
    op.create_index('ix_embedding_failures_next_retry_at', 'embedding_failures', ['next_retry_at'], unique=False)
    op.create_index('ix_personal_streaks_is_archived', 'personal_streaks', ['is_archived'], unique=False)
    op.create_index('ix_personal_streaks_category', 'personal_streaks', ['category'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_personal_streaks_category', table_name='personal_streaks')
    op.drop_index('ix_personal_streaks_is_archived', table_name='personal_streaks')
    op.drop_index('ix_embedding_failures_next_retry_at', table_name='embedding_failures')
    op.drop_index('ix_note_links_target_note_id', table_name='note_links')
    op.drop_index('ix_notes_updated_at', table_name='notes')
    op.drop_index('ix_notes_created_at', table_name='notes')
    op.drop_index('ix_goals_state', table_name='goals')
    op.drop_index('ix_goals_tag_id', table_name='goals')
    op.drop_index('ix_goals_note_id', table_name='goals')
    op.drop_index('ix_goals_parent_id', table_name='goals')
