import os
import tempfile
import unittest

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from services.tag_graph import rebuild_tag_cooccurrences


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
                text(
                    "INSERT INTO note_tags (note_id, tag_id) VALUES "
                    "(1, 1), (1, 2), "
                    "(2, 1), (2, 2), "
                    "(3, 1), (3, 3)"
                )
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
                text(
                    "SELECT tag_a_id, tag_b_id, weight "
                    "FROM tag_cooccurrences ORDER BY tag_a_id, tag_b_id"
                )
            ).fetchall()

        self.assertEqual(rows, [(1, 2, 2)])


if __name__ == "__main__":
    unittest.main()
