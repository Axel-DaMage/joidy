"""create_github_integration

Revision ID: 20260502_github_integration
Revises: 20260501_planning
Create Date: 2026-05-02

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '20260502_github_integration'
down_revision: Union[str, None] = '20260501_planning'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'github_repos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('full_name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('url', sa.String(500), nullable=False),
        sa.Column('default_branch', sa.String(100), nullable=True),
        sa.Column('is_private', sa.Boolean(), nullable=True),
        sa.Column('status', sa.String(20), nullable=True),
        sa.Column('webhook_id', sa.Integer(), nullable=True),
        sa.Column('webhook_secret', sa.String(100), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_github_repos_id'), 'github_repos', ['id'])
    op.create_index(op.f('ix_github_repos_full_name'), 'github_repos', ['full_name'], unique=True)

    op.create_table(
        'github_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('repo_id', sa.Integer(), sa.ForeignKey('github_repos.id'), nullable=False),
        sa.Column('external_id', sa.Integer(), nullable=False),
        sa.Column('item_type', sa.String(20), nullable=False),
        sa.Column('number', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('state', sa.String(20), nullable=True),
        sa.Column('state_reason', sa.String(50), nullable=True),
        sa.Column('author', sa.String(100), nullable=True),
        sa.Column('assignee', sa.String(100), nullable=True),
        sa.Column('labels', sa.String(500), nullable=True),
        sa.Column('url', sa.String(500), nullable=False),
        sa.Column('html_url', sa.String(500), nullable=False),
        sa.Column('goal_id', sa.Integer(), sa.ForeignKey('goals.id'), nullable=True),
        sa.Column('note_id', sa.Integer(), sa.ForeignKey('notes.id'), nullable=True),
        sa.Column('synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_github_items_id'), 'github_items', ['id'])
    op.create_index(op.f('ix_github_items_external_id'), 'github_items', ['external_id'])
    op.create_index(op.f('ix_github_items_repo_id'), 'github_items', ['repo_id'])
    op.create_index(op.f('ix_github_items_goal_id'), 'github_items', ['goal_id'])

    op.create_table(
        'github_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('repo_id', sa.Integer(), sa.ForeignKey('github_repos.id'), nullable=False),
        sa.Column('event_type', sa.String(30), nullable=False),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('sender', sa.String(100), nullable=False),
        sa.Column('item_type', sa.String(20), nullable=True),
        sa.Column('item_number', sa.Integer(), nullable=True),
        sa.Column('item_external_id', sa.Integer(), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('processed', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_github_events_id'), 'github_events', ['id'])
    op.create_index(op.f('ix_github_events_repo_id'), 'github_events', ['repo_id'])
    op.create_index(op.f('ix_github_events_created_at'), 'github_events', ['created_at'])


def downgrade() -> None:
    op.drop_table('github_events')
    op.drop_table('github_items')
    op.drop_table('github_repos')