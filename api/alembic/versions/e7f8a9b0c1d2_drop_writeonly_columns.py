"""drop write-only columns notes.is_embedded and note_tags.confidence/source

Revision ID: e7f8a9b0c1d2
Revises: c6d7e8f9a0b1
Create Date: 2026-11-26 00:00:00.000000

These columns were written but never read anywhere — dead writes costing
storage and IO on every note embedding and tag association (#1531):

- notes.is_embedded: set to true by ai-service store_embedding, but no
  code path filtered or returned it. Embedding state is derivable from
  the presence of a row in note_embeddings.
- note_tags.confidence / note_tags.source: populated on every NoteTag
  insert (``source="manual"|"ai"``, ``confidence=0.9``) but never read;
  ``note_to_response`` only serializes tag names.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7f8a9b0c1d2"
down_revision: str | None = "c6d7e8f9a0b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("notes", "is_embedded")
    op.drop_column("note_tags", "confidence")
    op.drop_column("note_tags", "source")


def downgrade() -> None:
    op.add_column(
        "note_tags",
        sa.Column("source", sa.String(length=20), server_default=sa.text("'manual'"), nullable=False),
    )
    op.add_column(
        "note_tags",
        sa.Column("confidence", sa.Float(), server_default=sa.text("1.0"), nullable=False),
    )
    op.add_column(
        "notes",
        sa.Column("is_embedded", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
