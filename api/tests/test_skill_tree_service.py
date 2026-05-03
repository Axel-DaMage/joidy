import os
import tempfile
import unittest
import sys
import types

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

if "sqlite_vec" not in sys.modules:
    sqlite_vec_stub = types.ModuleType("sqlite_vec")

    def _load(_connection):
        return None

    sqlite_vec_stub.load = _load
    sys.modules["sqlite_vec"] = sqlite_vec_stub

from services.skill_tree import sync_skills, sync_skills_for_tags


class SkillTreeServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.engine = create_engine(f"sqlite:///{self.db_path}")
        self.SessionLocal = sessionmaker(bind=self.engine)

        with self.engine.begin() as conn:
            conn.execute(text("CREATE TABLE tags (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"))
            conn.execute(text("CREATE TABLE note_tags (note_id INTEGER NOT NULL, tag_id INTEGER NOT NULL)"))
            conn.execute(
                text(
                    "CREATE TABLE skills ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                    "tag_id INTEGER NOT NULL, "
                    "note_count INTEGER NOT NULL DEFAULT 0, "
                    "level TEXT NOT NULL DEFAULT 'locked', "
                    "xp INTEGER NOT NULL DEFAULT 0, "
                    "first_unlocked_at DATETIME NULL, "
                    "updated_at DATETIME NULL)"
                )
            )

            conn.execute(text("INSERT INTO tags (id, name) VALUES (1, 'alpha'), (2, 'beta')"))
            conn.execute(text("INSERT INTO note_tags (note_id, tag_id) VALUES (1, 1), (2, 1), (3, 1)"))
            conn.execute(
                text(
                    "INSERT INTO skills (tag_id, note_count, level, xp, first_unlocked_at) "
                    "VALUES (1, 99, 'expert', 0, '2026-05-01 00:00:00'), (2, 4, 'apprentice', 0, '2026-05-01 00:00:00')"
                )
            )

    def tearDown(self) -> None:
        self.engine.dispose()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_sync_skills_updates_existing_rows_and_zero_counts(self) -> None:
        with self.SessionLocal() as db:
            updates = sync_skills(db)
            rows = db.execute(
                text("SELECT tag_id, note_count, level, first_unlocked_at FROM skills ORDER BY tag_id")
            ).fetchall()

        self.assertEqual(rows[0][0], 1)
        self.assertEqual(rows[0][1], 3)
        self.assertEqual(rows[0][2], 'apprentice')
        self.assertEqual(rows[1][0], 2)
        self.assertEqual(rows[1][1], 0)
        self.assertEqual(rows[1][2], 'locked')
        self.assertEqual(len(updates), 2)

    def test_sync_skills_for_tags_updates_only_requested_tags(self) -> None:
        with self.SessionLocal() as db:
            updates = sync_skills_for_tags(db, {1})
            rows = db.execute(
                text("SELECT tag_id, note_count, level FROM skills ORDER BY tag_id")
            ).fetchall()

        self.assertEqual(rows, [(1, 3, 'apprentice'), (2, 4, 'apprentice')])
        self.assertEqual(len(updates), 1)


if __name__ == "__main__":
    unittest.main()