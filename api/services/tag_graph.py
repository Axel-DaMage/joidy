from sqlalchemy import text
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

    params = {f"tag_{idx}": tag_id for idx, tag_id in enumerate(sorted(tag_ids))}
    placeholders = ", ".join(f":tag_{idx}" for idx in range(len(params)))

    db.execute(
        # Interpolates only generated :tag_N placeholders; values bind via params.
        text(f"DELETE FROM tag_cooccurrences WHERE tag_a_id IN ({placeholders}) OR tag_b_id IN ({placeholders})"),  # noqa: S608
        params,
    )

    # The pair set "{a,b}, a < b, with a or b touched" is partitioned into two
    # disjoint branches — touched tag on the low side, or on the high side with
    # an untouched low side. Splitting the former OR'd predicate into a UNION
    # ALL gives the planner a plain IN-filtered index scan per branch instead
    # of a cross-alias OR that tends to degenerate into a full note_tags scan
    # on hot tags (#1526).
    db.execute(
        text(
            f"""
            INSERT INTO tag_cooccurrences (tag_a_id, tag_b_id, weight)
            SELECT
                nt1.tag_id AS tag_a_id,
                nt2.tag_id AS tag_b_id,
                COUNT(DISTINCT nt1.note_id) AS weight
            FROM note_tags nt1
            JOIN note_tags nt2
              ON nt1.note_id = nt2.note_id
             AND nt1.tag_id < nt2.tag_id
            WHERE nt1.tag_id IN ({placeholders})
            GROUP BY nt1.tag_id, nt2.tag_id
            HAVING COUNT(DISTINCT nt1.note_id) >= 2
            UNION ALL
            SELECT
                nt1.tag_id AS tag_a_id,
                nt2.tag_id AS tag_b_id,
                COUNT(DISTINCT nt1.note_id) AS weight
            FROM note_tags nt1
            JOIN note_tags nt2
              ON nt1.note_id = nt2.note_id
             AND nt1.tag_id < nt2.tag_id
            WHERE nt2.tag_id IN ({placeholders})
              AND nt1.tag_id NOT IN ({placeholders})
            GROUP BY nt1.tag_id, nt2.tag_id
            HAVING COUNT(DISTINCT nt1.note_id) >= 2
            """  # noqa: S608 — only generated :tag_N placeholders are interpolated; values bind via params
        ),
        params,
    )
