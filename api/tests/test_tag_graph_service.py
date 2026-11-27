import os
import tempfile
import unittest

from services.tag_graph import (
    rebuild_tag_cooccurrences,
    sync_tag_cooccurrences_for_tags,
)
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


class TagGraphServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.engine = create_engine(f"sqlite:///{self.db_path}")
        self.SessionLocal = sessionmaker(bind=self.engine)

        with self.engine.begin() as conn:
            conn.execute(text("CREATE TABLE note_tags (note_id INTEGER NOT NULL, tag_id INTEGER NOT NULL)"))
            conn.execute(
                text(
                    "CREATE TABLE tag_cooccurrences ("
                    "tag_a_id INTEGER NOT NULL, "
                    "tag_b_id INTEGER NOT NULL, "
                    "weight INTEGER NOT NULL)"
                )
            )

            conn.execute(
                text("INSERT INTO note_tags (note_id, tag_id) VALUES (1, 1), (1, 2), (2, 1), (2, 2), (3, 1), (3, 3)")
            )

    def tearDown(self) -> None:
        self.engine.dispose()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_rebuild_tag_cooccurrences_creates_pairs_with_weight_threshold(self) -> None:
        with self.SessionLocal() as db:
            rebuild_tag_cooccurrences(db)
            db.commit()
            rows = db.execute(
                text("SELECT tag_a_id, tag_b_id, weight FROM tag_cooccurrences ORDER BY tag_a_id, tag_b_id")
            ).fetchall()

        self.assertEqual(rows, [(1, 2, 2)])

    def test_incremental_sync_updates_only_affected_pairs(self) -> None:
        with self.engine.begin() as conn:
            conn.execute(text("INSERT INTO note_tags (note_id, tag_id) VALUES (4, 1), (4, 2)"))

        with self.SessionLocal() as db:
            sync_tag_cooccurrences_for_tags(db, {1, 2})
            db.commit()
            rows = db.execute(
                text("SELECT tag_a_id, tag_b_id, weight FROM tag_cooccurrences ORDER BY tag_a_id, tag_b_id")
            ).fetchall()

        self.assertEqual(rows, [(1, 2, 3)])

    def test_incremental_sync_covers_pairs_where_touched_tag_is_the_high_side(self) -> None:
        """A touched tag appearing only as tag_b must still get its pairs
        rebuilt, while pairs between two untouched tags stay out (#1526)."""
        with self.engine.begin() as conn:
            # Notes 4 and 5 give pair (2, 3) a weight of 2. Pair (1, 2)
            # already co-occurs on notes 1-2 but neither side is touched.
            conn.execute(text("INSERT INTO note_tags (note_id, tag_id) VALUES (4, 2), (4, 3), (5, 2), (5, 3)"))

        with self.SessionLocal() as db:
            sync_tag_cooccurrences_for_tags(db, {3})
            db.commit()
            rows = db.execute(
                text("SELECT tag_a_id, tag_b_id, weight FROM tag_cooccurrences ORDER BY tag_a_id, tag_b_id")
            ).fetchall()

        self.assertEqual(rows, [(2, 3, 2)])

    def test_incremental_sync_does_not_duplicate_pairs_when_both_sides_touched(self) -> None:
        """When both tags of a pair are in the sync set, the pair must be
        inserted exactly once — the two query branches are disjoint (#1526)."""
        with self.engine.begin() as conn:
            conn.execute(text("INSERT INTO note_tags (note_id, tag_id) VALUES (4, 1), (4, 3)"))

        with self.SessionLocal() as db:
            sync_tag_cooccurrences_for_tags(db, {1, 3})
            db.commit()
            rows = db.execute(
                text("SELECT tag_a_id, tag_b_id, weight FROM tag_cooccurrences ORDER BY tag_a_id, tag_b_id")
            ).fetchall()

        # (1, 3) lands once even though both its tags are in the sync set;
        # (1, 2) is rebuilt because tag 1 is touched.
        self.assertEqual(rows, [(1, 2, 2), (1, 3, 2)])


if __name__ == "__main__":
    unittest.main()
