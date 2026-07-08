"""create_planning_assignments

Revision ID: 20260501_planning
Revises: 20260427_consolidated
Create Date: 2026-05-01
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260501_planning'
down_revision: str | None = '20260427_consolidated'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'planning_assignments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('goal_id', sa.Integer(), sa.ForeignKey('goals.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_planning_assignments_date'), 'planning_assignments', ['date'], unique=False)
    op.create_index(op.f('ix_planning_assignments_id'), 'planning_assignments', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_planning_assignments_id'), table_name='planning_assignments')
    op.drop_index(op.f('ix_planning_assignments_date'), table_name='planning_assignments')
    op.drop_table('planning_assignments')
