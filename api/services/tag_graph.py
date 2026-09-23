from repositories import TagCooccurrenceRepository
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session


def rebuild_tag_cooccurrences(db: Session) -> None:
    """Recompute tag co-occurrence matrix from note_tags.

    This shifts heavy pairwise work to write paths so read paths stay fast.
    """
    db.execute(text("DELETE FROM tag_cooccurrences"))
    db.execute(
        text(
            """
            INSERT INTO tag_cooccurrences (tag_a_id, tag_b_id, weight)
            SELECT
                nt1.tag_id AS tag_a_id,
                nt2.tag_id AS tag_b_id,
                COUNT(DISTINCT nt1.note_id) AS weight
            FROM note_tags nt1
            JOIN note_tags nt2
              ON nt1.note_id = nt2.note_id
             AND nt1.tag_id < nt2.tag_id
            GROUP BY nt1.tag_id, nt2.tag_id
            HAVING COUNT(DISTINCT nt1.note_id) >= 2
            """
        )
    )


def sync_tag_cooccurrences_for_tags(db: Session, tag_ids: set[int]) -> None:
    """Recompute only the co-occurrence pairs that involve the given tags."""
    if not tag_ids:
        return

    tag_list = list(tag_ids)

    stmt_del = text(
        "DELETE FROM tag_cooccurrences WHERE tag_a_id IN :tag_ids OR tag_b_id IN :tag_ids"
    ).bindparams(bindparam("tag_ids", expanding=True))
    db.execute(stmt_del, {"tag_ids": tag_list})

    stmt_ins = text(
        """
        INSERT INTO tag_cooccurrences (tag_a_id, tag_b_id, weight)
        SELECT
            nt1.tag_id AS tag_a_id,
            nt2.tag_id AS tag_b_id,
            COUNT(DISTINCT nt1.note_id) AS weight
        FROM note_tags nt1
        JOIN note_tags nt2
          ON nt1.note_id = nt2.note_id
         AND nt1.tag_id < nt2.tag_id
        WHERE nt1.tag_id IN :tag_ids
           OR nt2.tag_id IN :tag_ids
        GROUP BY nt1.tag_id, nt2.tag_id
        HAVING COUNT(DISTINCT nt1.note_id) >= 2
        """
    ).bindparams(bindparam("tag_ids", expanding=True))
    db.execute(stmt_ins, {"tag_ids": tag_list})
