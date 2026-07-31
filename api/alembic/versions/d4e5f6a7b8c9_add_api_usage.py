"""add api_usage table for ai-service cost tracking

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-31 19:00:00.000000

The ai-service cost_tracker previously wrote to a stale SQLite file
(/data/db/joidy.db) that never worked after the PostgreSQL migration (#273).
This migration creates the api_usage table in the shared PostgreSQL database
so cost/usage tracking actually persists.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'api_usage',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('operation', sa.String(length=50), nullable=False),
        sa.Column('input_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('output_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_api_usage_created_at',
        'api_usage',
        ['created_at'],
        unique=False,
    )
    op.create_index(
        'ix_api_usage_operation',
        'api_usage',
        ['operation'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_api_usage_operation', table_name='api_usage')
    op.drop_index('ix_api_usage_created_at', table_name='api_usage')
    op.drop_table('api_usage')
