"""cleanup_hex_named_tags

Remove tags whose name is a bare hex color code (e.g. "ef4444", "c8a96e")
that were accidentally created from Obsidian frontmatter color fields.
Also cleans up dependent rows in note_tags, skills, and tag_cooccurrences.

Revision ID: a1b2c3d4e5f6
Revises: bce8f3a471d1
Create Date: 2026-07-30 23:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'bce8f3a471d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Tags whose name is a 6-character hex string (e.g. "ef4444", "c8a96e").
    # These are color values misused as tag names (#268).
    hex_pattern = r'^[0-9a-f]{6}$'

    # 1. Nullify goal.tag_id references to hex-named tags
    op.execute(
        sa.text(
            "UPDATE goals SET tag_id = NULL WHERE tag_id IN ("
            "  SELECT id FROM tags WHERE name ~ :pattern"
            ")"
        ).bindparams(pattern=hex_pattern)
    )

    # 2. Nullify parent_id references to hex-named tags
    op.execute(
        sa.text(
            "UPDATE tags SET parent_id = NULL WHERE parent_id IN ("
            "  SELECT id FROM tags WHERE name ~ :pattern"
            ")"
        ).bindparams(pattern=hex_pattern)
    )

    # 3. Delete skills associated with hex-named tags
    op.execute(
        sa.text(
            "DELETE FROM skills WHERE tag_id IN ("
            "  SELECT id FROM tags WHERE name ~ :pattern"
            ")"
        ).bindparams(pattern=hex_pattern)
    )

    # 4. Delete tag co-occurrences referencing hex-named tags
    op.execute(
        sa.text(
            "DELETE FROM tag_cooccurrences WHERE tag_a_id IN ("
            "  SELECT id FROM tags WHERE name ~ :pattern"
            ") OR tag_b_id IN ("
            "  SELECT id FROM tags WHERE name ~ :pattern"
            ")"
        ).bindparams(pattern=hex_pattern)
    )

    # 5. Delete note-tag associations for hex-named tags
    op.execute(
        sa.text(
            "DELETE FROM note_tags WHERE tag_id IN ("
            "  SELECT id FROM tags WHERE name ~ :pattern"
            ")"
        ).bindparams(pattern=hex_pattern)
    )

    # 6. Delete the hex-named tags themselves
    op.execute(
        sa.text("DELETE FROM tags WHERE name ~ :pattern").bindparams(pattern=hex_pattern)
    )


def downgrade() -> None:
    # Data migration — not reversible.
    pass
