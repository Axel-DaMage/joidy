"""add_max_assignment_days

Revision ID: 20260503_add_max_assignment_days
Revises: 20260502_github_integration
Create Date: 2026-05-03

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '20260503_add_max_assignment_days'
down_revision: Union[str, None] = '20260502_github_integration'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('goals', sa.Column('max_assignment_days', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('goals', 'max_assignment_days')
