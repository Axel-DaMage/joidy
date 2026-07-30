"""add sync_state

Revision ID: 8261da3f5e9d
Revises: 2f638d55375d
Create Date: 2026-07-30 02:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8261da3f5e9d'
down_revision: Union[str, None] = '2f638d55375d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'sync_state',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('note_id', sa.Integer(), nullable=False),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('local_mtime', sa.DateTime(), nullable=True),
        sa.Column('remote_mtime', sa.DateTime(), nullable=True),
        sa.Column('conflict', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['note_id'], ['notes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('note_id')
    )
    op.create_index(op.f('ix_sync_state_id'), 'sync_state', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_sync_state_id'), table_name='sync_state')
    op.drop_table('sync_state')
