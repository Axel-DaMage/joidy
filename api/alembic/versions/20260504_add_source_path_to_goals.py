"""add_source_path_to_goals

Revision ID: 20260504_add_source_path_to_goals
Revises: 20260503_add_max_assignment_days
Create Date: 2026-05-04

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '20260504_add_source_path_to_goals'
down_revision: Union[str, None] = '20260503_add_max_assignment_days'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('goals', sa.Column('source_path', sa.String(1000), nullable=True))


def downgrade() -> None:
    op.drop_column('goals', 'source_path')