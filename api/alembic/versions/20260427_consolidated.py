"""consolidated_goals_schema

Revision ID: 20260427_consolidated
Revises: 20260421_000003
Create Date: 2026-04-27
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260427_consolidated'
down_revision: str | None = '20260421_000003'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    from sqlalchemy import inspect as sa_inspect
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    existing_tables = inspector.get_table_names()
    existing_goal_cols = [c['name'] for c in inspector.get_columns('goals')] if 'goals' in existing_tables else []

    # Safely drop tables/indexes that may not exist
    if 'note_embeddings' in existing_tables:
        op.drop_table('note_embeddings')
    try:
        op.drop_index('ix_embedding_failures_next_retry_at', table_name='embedding_failures')
    except Exception:
        pass

    # Add goal columns if they don't already exist
    new_cols = {
        'temporality': sa.Column('temporality', sa.String(20), nullable=False, server_default='DAILY'),
        'measurement_type': sa.Column('measurement_type', sa.String(20), nullable=False, server_default='COUNT'),
        'target_value': sa.Column('target_value', sa.Float(), nullable=False, server_default='1.0'),
        'current_value': sa.Column('current_value', sa.Float(), nullable=False, server_default='0.0'),
        'state': sa.Column('state', sa.String(20), nullable=False, server_default='ACTIVE'),
        'fail_config': sa.Column('fail_config', sa.String(20), nullable=False, server_default='STATIC'),
        'fail_emoji': sa.Column('fail_emoji', sa.String(20), nullable=False, server_default='🔴'),
        'color': sa.Column('color', sa.String(20), nullable=False, server_default='#c8a96e'),
        'theme': sa.Column('theme', sa.String(20), nullable=False, server_default='solid'),
        'note_id': sa.Column('note_id', sa.Integer(), nullable=True),
        'parent_id': sa.Column('parent_id', sa.Integer(), nullable=True),
        'pending_removal': sa.Column('pending_removal', sa.Boolean(), nullable=False, server_default=sa.text('0')),
    }

    for col_name, col_def in new_cols.items():
        if col_name not in existing_goal_cols:
            op.add_column('goals', col_def)

    # Drop old column
    if 'target_notes' in existing_goal_cols:
        with op.batch_alter_table('goals') as batch_op:
            batch_op.drop_column('target_notes')

    try:
        op.drop_index('ix_tag_cooccurrences_weight', table_name='tag_cooccurrences')
    except Exception:
        pass


def downgrade() -> None:
    cols_to_drop = [
        'pending_removal', 'parent_id', 'note_id', 'theme', 'color',
        'fail_emoji', 'fail_config', 'state', 'current_value',
        'target_value', 'measurement_type', 'temporality',
    ]
    with op.batch_alter_table('goals') as batch_op:
        for col in cols_to_drop:
            try:
                batch_op.drop_column(col)
            except Exception:
                pass
    op.add_column('goals', sa.Column('target_notes', sa.INTEGER(), nullable=False, server_default='0'))
