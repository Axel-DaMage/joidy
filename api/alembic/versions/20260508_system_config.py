"""Add system_config table

Revision ID: 20260508_system_config
Revises: 20260507_graph_indices
Create Date: 2025-05-08

"""
from alembic import op
import sqlalchemy as sa


revision = '20260508_system_config'
down_revision = '20260507_graph_indices'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'system_config',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(), nullable=False),
        sa.Column('value', sa.String(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_system_config_key'), 'system_config', ['key'], unique=True)
    op.create_index(op.f('ix_system_config_id'), 'system_config', ['id'], unique=False)

    # Insert default XP values
    op.execute("""
        INSERT INTO system_config (key, value) VALUES
        ('xp_note_created', '10'),
        ('xp_note_edited', '5'),
        ('xp_tag_added', '3'),
        ('xp_tag_accepted_ai', '4'),
        ('xp_topic_connected', '8'),
        ('xp_goal_completed', '50'),
        ('xp_daily_activity', '15'),
        ('xp_streak_milestone_7', '100'),
        ('xp_streak_milestone_30', '100'),
        ('xp_streak_milestone_100', '100'),
        ('xp_note_imported_obsidian', '2'),
        ('plant_stage_0', '0'),
        ('plant_stage_1', '300'),
        ('plant_stage_2', '1200'),
        ('plant_stage_3', '4000'),
        ('plant_stage_4', '10000'),
        ('plant_stage_5', '25000'),
        ('plant_stage_6', '60000')
    """)


def downgrade() -> None:
    op.drop_index(op.f('ix_system_config_id'), table_name='system_config')
    op.drop_index(op.f('ix_system_config_key'), table_name='system_config')
    op.drop_table('system_config')