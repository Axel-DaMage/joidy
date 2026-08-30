"""db_perf_opts

Revision ID: 256cd4e9a94a
Revises: a7b8c9d0e1f2
Create Date: 2026-08-30 02:22:10.091887
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '256cd4e9a94a'
down_revision: Union[str, None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. HNSW Index for pgvector
    op.execute("CREATE INDEX IF NOT EXISTS ix_note_embeddings_hnsw ON note_embeddings USING hnsw (embedding vector_cosine_ops)")
    
    # 2. Partial index on personal_streaks
    op.execute("CREATE INDEX IF NOT EXISTS ix_personal_streaks_active ON personal_streaks (id) WHERE is_archived = FALSE")
    
    # 3. Index on streak_checkins
    op.execute("CREATE INDEX IF NOT EXISTS ix_streak_checkins_query ON streak_checkins (streak_id, check_date)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_note_embeddings_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_personal_streaks_active")
    op.execute("DROP INDEX IF EXISTS ix_streak_checkins_query")
