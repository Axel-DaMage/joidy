"""Unit tests for joidy_vault_writer — vault file I/O, markdown generation,
goal file CRUD, daily journal writing, and goal restoration from vault.

The vault writer is the core integration between Joidy and Obsidian: it writes
Joidy-owned files into _joidy/ and Objetivos/ inside the vault. Bugs here could
corrupt user vault files or lose goal data (#402). All filesystem operations use
tempfile.TemporaryDirectory so tests never touch a real vault.
"""

import sys
import tempfile
import types
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Stub sqlite_vec before importing app modules (matches conftest pattern).
if "sqlite_vec" not in sys.modules:
    _stub = types.ModuleType("sqlite_vec")
    _stub.load = lambda _conn: None  # type: ignore
    sys.modules["sqlite_vec"] = _stub

from config import settings
from database import Base
from models.gamification import StreakRecord, UserStats
from models.goal import Goal
from models.note import Note, NoteTag, Tag
from models.skill import Skill
import services.joidy_vault_writer as vault_writer
from services.joidy_vault_writer import (
    JOIDY_DIR,
    JOIDY_HEADER,
    OBJECTIVES_DIR,
    _parse_goal_content,
    delete_goal_file,
    get_objectives_dir,
    get_vault_path,
    read_goal_file,
    restore_goals_from_vault,
    slugify,
    update_goal_file,
    write_daily,
    write_objectives,
    write_readme,
    write_skills,
)


class VaultWriterTestBase(unittest.TestCase):
    """Base class with a temporary vault directory and in-memory SQLite DB."""

    def setUp(self) -> None:
        self._orig_vault = settings.obsidian_vault_path
        self._tmpdir = tempfile.TemporaryDirectory()
        settings.obsidian_vault_path = self._tmpdir.name

        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        with self.engine.begin() as conn:
            try:
                conn.execute(
                    text(
                        "CREATE TABLE IF NOT EXISTS tag_cooccurrences "
                        "(tag_a_id INTEGER, tag_b_id INTEGER, weight INTEGER, "
                        "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
                    )
                )
            except Exception:
                pass
        self.Session = sessionmaker(bind=self.engine)

    def tearDown(self) -> None:
        settings.obsidian_vault_path = self._orig_vault
        self._tmpdir.cleanup()
        self.engine.dispose()


class GetVaultPathTest(VaultWriterTestBase):
    def test_returns_path_when_vault_exists(self) -> None:
        path = get_vault_path()
        self.assertIsNotNone(path)
        self.assertTrue(path.exists())

    def test_returns_none_when_vault_not_set(self) -> None:
        settings.obsidian_vault_path = ""
        self.assertIsNone(get_vault_path())

    def test_returns_none_when_vault_does_not_exist(self) -> None:
        settings.obsidian_vault_path = "/nonexistent/path/that/does/not/exist"
        self.assertIsNone(get_vault_path())


class GetObjectivesDirTest(VaultWriterTestBase):
    def test_creates_objectives_dir(self) -> None:
        obj_dir = get_objectives_dir()
        self.assertIsNotNone(obj_dir)
        self.assertTrue(obj_dir.exists())
        self.assertEqual(obj_dir.name, OBJECTIVES_DIR)

    def test_returns_none_when_no_vault(self) -> None:
        settings.obsidian_vault_path = ""
        self.assertIsNone(get_objectives_dir())


class SlugifyTest(unittest.TestCase):
    def test_lowercases_text(self) -> None:
        self.assertEqual(slugify("Hello World"), "hello-world")

    def test_replaces_spaces_with_hyphens(self) -> None:
        self.assertEqual(slugify("my  goal"), "my-goal")

    def test_replaces_underscores_with_hyphens(self) -> None:
        self.assertEqual(slugify("my_goal"), "my-goal")

    def test_strips_special_chars(self) -> None:
        self.assertEqual(slugify("goal! @#$%"), "goal")

    def test_collapses_multiple_hyphens(self) -> None:
        self.assertEqual(slugify("a---b"), "a-b")

    def test_strips_leading_trailing_hyphens(self) -> None:
        self.assertEqual(slugify("--test--"), "test")

    def test_empty_string(self) -> None:
        self.assertEqual(slugify(""), "")


class ParseGoalContentTest(unittest.TestCase):
    def test_parses_frontmatter_and_body(self) -> None:
        content = "---\ngoal_id: 1\ntitle: My Goal\njoidy_managed: true\n---\n# My Goal\n\nDescription here"
        parsed = _parse_goal_content(content)
        self.assertEqual(parsed["goal_id"], "1")
        self.assertEqual(parsed["title"], "My Goal")
        self.assertEqual(parsed["joidy_managed"], "true")
        self.assertEqual(parsed["content"], "Description here")

    def test_falls_back_to_heading_title(self) -> None:
        content = "---\n---\n# Heading Title\n\nBody text"
        parsed = _parse_goal_content(content)
        self.assertEqual(parsed["title"], "Heading Title")
        self.assertEqual(parsed["content"], "Body text")

    def test_no_frontmatter(self) -> None:
        content = "# Just a Title\n\nBody"
        parsed = _parse_goal_content(content)
        self.assertEqual(parsed["title"], "Just a Title")
        self.assertEqual(parsed["content"], "Body")


class UpdateGoalFileTest(VaultWriterTestBase):
    def test_creates_new_goal_file(self) -> None:
        result = update_goal_file(1, "My Goal", "Description", {"temporality": "DAILY"})
        self.assertTrue(result)

        obj_dir = get_objectives_dir()
        files = list(obj_dir.glob("1_*.md"))
        self.assertEqual(len(files), 1)
        content = files[0].read_text(encoding="utf-8")
        self.assertIn("goal_id: 1", content)
        self.assertIn("joidy_managed: True", content)
        self.assertIn("# My Goal", content)
        self.assertIn("Description", content)

    def test_updates_existing_goal_file(self) -> None:
        update_goal_file(2, "Original Title", "Original", {"state": "ACTIVE"})
        update_goal_file(2, "Updated Title", "Updated content", {"state": "COMPLETED"})

        obj_dir = get_objectives_dir()
        files = list(obj_dir.glob("2_*.md"))
        self.assertEqual(len(files), 1)
        content = files[0].read_text(encoding="utf-8")
        self.assertIn("# Updated Title", content)
        self.assertIn("Updated content", content)
        self.assertIn("state: COMPLETED", content)

    def test_metadata_none_values_excluded(self) -> None:
        update_goal_file(3, "Goal", "Body", {"note_id": None, "tag_id": 5})
        obj_dir = get_objectives_dir()
        content = list(obj_dir.glob("3_*.md"))[0].read_text(encoding="utf-8")
        self.assertNotIn("note_id", content)
        self.assertIn("tag_id: 5", content)

    def test_returns_false_when_no_vault(self) -> None:
        settings.obsidian_vault_path = ""
        result = update_goal_file(1, "Goal", "Body", {})
        self.assertFalse(result)


class ReadGoalFileTest(VaultWriterTestBase):
    def test_reads_existing_goal_file(self) -> None:
        # Write a goal file directly with frontmatter title (the format
        # _parse_goal_content expects for title extraction).
        obj_dir = get_objectives_dir()
        filepath = obj_dir / "5_readable-goal.md"
        filepath.write_text(
            "---\ngoal_id: 5\ntitle: Readable Goal\nstate: ACTIVE\n---\n# Readable Goal\n\nContent here",
            encoding="utf-8",
        )
        parsed = read_goal_file(5)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["title"], "Readable Goal")
        self.assertEqual(parsed["content"], "Content here")
        self.assertEqual(parsed["state"], "ACTIVE")

    def test_reads_goal_file_with_heading_title(self) -> None:
        """When no frontmatter title, the H1 heading is used as fallback."""
        obj_dir = get_objectives_dir()
        filepath = obj_dir / "6_heading-title.md"
        filepath.write_text(
            "---\ngoal_id: 6\n---\n# Heading Title\n\nBody text",
            encoding="utf-8",
        )
        parsed = read_goal_file(6)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["title"], "Heading Title")
        self.assertEqual(parsed["content"], "Body text")

    def test_returns_none_when_goal_not_found(self) -> None:
        self.assertIsNone(read_goal_file(999))

    def test_returns_none_when_no_vault(self) -> None:
        settings.obsidian_vault_path = ""
        self.assertIsNone(read_goal_file(1))


class DeleteGoalFileTest(VaultWriterTestBase):
    def test_deletes_existing_goal_file(self) -> None:
        update_goal_file(7, "Delete Me", "Content", {})
        self.assertTrue(delete_goal_file(7))

        obj_dir = get_objectives_dir()
        self.assertEqual(len(list(obj_dir.glob("7_*.md"))), 0)

    def test_returns_false_when_goal_not_found(self) -> None:
        self.assertFalse(delete_goal_file(999))

    def test_returns_false_when_no_vault(self) -> None:
        settings.obsidian_vault_path = ""
        self.assertFalse(delete_goal_file(1))


class WriteObjectivesTest(VaultWriterTestBase):
    def test_writes_all_goals_to_vault(self) -> None:
        with self.Session() as db:
            db.add(Goal(id=1, title="First Goal", description="Desc 1"))
            db.add(Goal(id=2, title="Second Goal", description="Desc 2"))
            db.commit()

            result = write_objectives(db)
            self.assertTrue(result)

        obj_dir = get_objectives_dir()
        files = sorted(obj_dir.glob("*.md"))
        self.assertEqual(len(files), 2)
        content1 = files[0].read_text(encoding="utf-8")
        self.assertIn("goal_id: 1", content1)
        self.assertIn("# First Goal", content1)

    def test_returns_false_when_no_vault(self) -> None:
        settings.obsidian_vault_path = ""
        with self.Session() as db:
            self.assertFalse(write_objectives(db))


class WriteDailyTest(VaultWriterTestBase):
    def test_writes_daily_journal(self) -> None:
        target = date(2025, 6, 15)
        with self.Session() as db:
            db.add(UserStats(id=1, total_xp=500, current_streak=7))
            db.commit()
            result = write_daily(db, target_date=target)
            self.assertTrue(result)

        daily_path = Path(settings.obsidian_vault_path) / JOIDY_DIR / "daily" / "2025-06-15.md"
        self.assertTrue(daily_path.exists())
        content = daily_path.read_text(encoding="utf-8")
        self.assertIn(JOIDY_HEADER, content)
        self.assertIn("date: 2025-06-15", content)
        self.assertIn("Daily Journal", content)
        self.assertIn("XP ganado: **0**", content)
        self.assertIn("Racha: **7 días**", content)

    def test_daily_includes_streak_xp(self) -> None:
        target = date(2025, 6, 15)
        with self.Session() as db:
            db.add(UserStats(id=1, total_xp=100, current_streak=3))
            db.add(StreakRecord(activity_date=target, xp_earned=25))
            db.commit()
            write_daily(db, target_date=target)

        content = (Path(settings.obsidian_vault_path) / JOIDY_DIR / "daily" / "2025-06-15.md").read_text("utf-8")
        self.assertIn("xp_earned: 25", content)
        self.assertIn("XP ganado: **25**", content)

    def test_returns_false_when_no_vault(self) -> None:
        settings.obsidian_vault_path = ""
        with self.Session() as db:
            self.assertFalse(write_daily(db))


class WriteSkillsTest(VaultWriterTestBase):
    def test_writes_skills_file(self) -> None:
        with self.Session() as db:
            tag = Tag(name="python")
            db.add(tag)
            db.flush()
            db.add(Skill(tag_id=tag.id, note_count=5, level="journeyman"))
            db.commit()

            result = write_skills(db)
            self.assertTrue(result)

        skills_path = Path(settings.obsidian_vault_path) / JOIDY_DIR / "skills.md"
        self.assertTrue(skills_path.exists())
        content = skills_path.read_text(encoding="utf-8")
        self.assertIn(JOIDY_HEADER, content)
        self.assertIn("Árbol de Habilidades", content)
        self.assertIn("python", content)

    def test_writes_empty_skills_message(self) -> None:
        with self.Session() as db:
            write_skills(db)

        content = (Path(settings.obsidian_vault_path) / JOIDY_DIR / "skills.md").read_text("utf-8")
        self.assertIn("Sin habilidades aún", content)

    def test_returns_false_when_no_vault(self) -> None:
        settings.obsidian_vault_path = ""
        with self.Session() as db:
            self.assertFalse(write_skills(db))


class WriteReadmeTest(VaultWriterTestBase):
    def test_writes_readme_if_not_exists(self) -> None:
        vault = Path(settings.obsidian_vault_path)
        write_readme(vault)
        readme = vault / JOIDY_DIR / "README.md"
        self.assertTrue(readme.exists())
        content = readme.read_text(encoding="utf-8")
        self.assertIn("Carpeta administrada por Joidy", content)

    def test_does_not_overwrite_existing_readme(self) -> None:
        vault = Path(settings.obsidian_vault_path)
        joidy_dir = vault / JOIDY_DIR
        joidy_dir.mkdir(parents=True, exist_ok=True)
        readme = joidy_dir / "README.md"
        readme.write_text("custom content", encoding="utf-8")

        write_readme(vault)
        self.assertEqual(readme.read_text(encoding="utf-8"), "custom content")


class RestoreGoalsFromVaultTest(VaultWriterTestBase):
    def test_restores_missing_goals(self) -> None:
        # Write a joidy_managed goal file directly with frontmatter title
        # (the format restore_goals_from_vault expects).
        obj_dir = get_objectives_dir()
        (obj_dir / "10_restored-goal.md").write_text(
            "---\n"
            "goal_id: 10\n"
            "joidy_managed: true\n"
            "title: Restored Goal\n"
            "temporality: WEEKLY\n"
            "measurement_type: COUNT\n"
            "target_value: 5.0\n"
            "current_value: 2.0\n"
            "state: ACTIVE\n"
            "fail_config: STATIC\n"
            "fail_emoji: \U0001f534\n"
            "color: #c8a96e\n"
            "theme: solid\n"
            "---\n"
            "# Restored Goal\n\nDescription",
            encoding="utf-8",
        )

        with self.Session() as db:
            result = restore_goals_from_vault(db)
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["restored"], 1)
            self.assertEqual(result["skipped"], 0)

            goal = db.query(Goal).filter(Goal.id == 10).first()
            self.assertIsNotNone(goal)
            self.assertEqual(goal.title, "Restored Goal")
            self.assertEqual(goal.description, "Description")

    def test_skips_existing_goals(self) -> None:
        obj_dir = get_objectives_dir()
        (obj_dir / "11_existing-goal.md").write_text(
            "---\ngoal_id: 11\njoidy_managed: true\ntitle: Vault Goal\n---\n# Vault Goal\n\nDesc",
            encoding="utf-8",
        )

        with self.Session() as db:
            db.add(Goal(id=11, title="Already in DB", description="DB desc"))
            db.commit()
            result = restore_goals_from_vault(db)
            self.assertEqual(result["restored"], 0)
            self.assertEqual(result["skipped"], 1)

            goal = db.query(Goal).filter(Goal.id == 11).first()
            self.assertEqual(goal.title, "Already in DB")

    def test_ignores_non_joidy_files(self) -> None:
        obj_dir = get_objectives_dir()
        (obj_dir / "manual_note.md").write_text("---\n---\n# Manual Note\n\nNot joidy managed", encoding="utf-8")

        with self.Session() as db:
            result = restore_goals_from_vault(db)
            self.assertEqual(result["restored"], 0)

    def test_returns_no_vault_when_path_unset(self) -> None:
        settings.obsidian_vault_path = ""
        with self.Session() as db:
            result = restore_goals_from_vault(db)
            self.assertEqual(result["status"], "no_vault")


class FilePathHandlingTest(VaultWriterTestBase):
    def test_goal_file_uses_slugified_filename(self) -> None:
        update_goal_file(20, "My Complex Goal Title!", "Content", {})
        obj_dir = get_objectives_dir()
        files = list(obj_dir.glob("20_*.md"))
        self.assertEqual(len(files), 1)
        self.assertIn("my-complex-goal-title", files[0].name)

    def test_joidy_dir_created_on_daily_write(self) -> None:
        with self.Session() as db:
            write_daily(db, target_date=date(2025, 1, 1))
        joidy_dir = Path(settings.obsidian_vault_path) / JOIDY_DIR
        self.assertTrue(joidy_dir.exists())
        self.assertTrue((joidy_dir / "daily").exists())

    def test_joidy_dir_created_on_skills_write(self) -> None:
        with self.Session() as db:
            write_skills(db)
        joidy_dir = Path(settings.obsidian_vault_path) / JOIDY_DIR
        self.assertTrue(joidy_dir.exists())


if __name__ == "__main__":
    unittest.main()
