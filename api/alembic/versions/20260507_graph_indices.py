"""add_graph_and_performance_indices

Revision ID: 20260507_graph_indices
Revises: 20260504_add_source_path_to_goals
Create Date: 2026-05-07

Adds database indices to optimize:
- Tag graph co-occurrence queries
- Skill tree lookups by tag_id
- Note tag queries for graph rendering
- XP events temporal queries
- Embedding failure retry scheduling
"""
from collections.abc import Sequence

from alembic import op

revision: str = '20260507_graph_indices'
down_revision: str | None = '20260504_add_source_path_to_goals'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Tag co-occurrence graph: speed up joins by tag pair
    op.create_index('ix_tag_cooccurrences_tag_a', 'tag_cooccurrences', ['tag_a_id'], if_not_exists=True)
    op.create_index('ix_tag_cooccurrences_tag_b', 'tag_cooccurrences', ['tag_b_id'], if_not_exists=True)

    # Note-Tag junction: optimize tag-based note lookups
    op.create_index('ix_note_tags_tag_id', 'note_tags', ['tag_id'], if_not_exists=True)
    op.create_index('ix_note_tags_note_id', 'note_tags', ['note_id'], if_not_exists=True)

    # Skill tree: fast lookup by tag_id (already UNIQUE but explicit index helps)
    op.create_index('ix_skills_tag_id', 'skills', ['tag_id'], if_not_exists=True)

    # XP events: temporal ordering for recent-events queries
    op.create_index('ix_xp_events_created_at', 'xp_events', ['created_at'], if_not_exists=True)
    op.create_index('ix_xp_events_event_type', 'xp_events', ['event_type'], if_not_exists=True)

    # Streak records: date lookups
    op.create_index('ix_streak_records_activity_date', 'streak_records', ['activity_date'], if_not_exists=True)

    # Embedding failures: retry scheduling queries
    op.create_index('ix_embedding_failures_next_retry', 'embedding_failures', ['next_retry_at'], if_not_exists=True)
    op.create_index('ix_embedding_failures_attempts', 'embedding_failures', ['attempts'], if_not_exists=True)

    # Goals: state-based filtering and temporal queries
    op.create_index('ix_goals_state', 'goals', ['state'], if_not_exists=True)
    op.create_index('ix_goals_temporality', 'goals', ['temporality'], if_not_exists=True)
    op.create_index('ix_goals_note_id', 'goals', ['note_id'], if_not_exists=True)

    # Note links: graph traversal
    op.create_index('ix_note_links_target', 'note_links', ['target_note_id'], if_not_exists=True)


def downgrade() -> None:
    op.drop_index('ix_note_links_target', table_name='note_links')
    op.drop_index('ix_goals_note_id', table_name='goals')
    op.drop_index('ix_goals_temporality', table_name='goals')
    op.drop_index('ix_goals_state', table_name='goals')
    op.drop_index('ix_embedding_failures_attempts', table_name='embedding_failures')
    op.drop_index('ix_embedding_failures_next_retry', table_name='embedding_failures')
    op.drop_index('ix_streak_records_activity_date', table_name='streak_records')
    op.drop_index('ix_xp_events_event_type', table_name='xp_events')
    op.drop_index('ix_xp_events_created_at', table_name='xp_events')
    op.drop_index('ix_skills_tag_id', table_name='skills')
    op.drop_index('ix_note_tags_note_id', table_name='note_tags')
    op.drop_index('ix_note_tags_tag_id', table_name='note_tags')
    op.drop_index('ix_tag_cooccurrences_tag_b', table_name='tag_cooccurrences')
    op.drop_index('ix_tag_cooccurrences_tag_a', table_name='tag_cooccurrences')
