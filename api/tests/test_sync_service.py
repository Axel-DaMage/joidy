"""Unit tests for sync_service — conflict detection, listing, and resolution."""

import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

if "sqlite_vec" not in sys.modules:
    _stub = types.ModuleType("sqlite_vec")
    _stub.load = lambda _conn: None  # type: ignore
    sys.modules["sqlite_vec"] = _stub

from database import Base
from models.note import Note
from models.sync_state import SyncState
from services.sync_service import (
    CONFLICT_TOLERANCE_SECONDS,
    detect_conflict,
    list_conflicts,
    resolve_conflict,
    update_local_mtime,
)


class SyncServiceTestBase(unittest.TestCase):
    """Base class with in-memory SQLite setup."""

    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        with self.engine.begin() as conn:
            try:
                conn.execute(text(
                    "CREATE TABLE IF NOT EXISTS tag_cooccurrences "
                    "(tag_a_id INTEGER, tag_b_id INTEGER, weight INTEGER, "
                    "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
                ))
            except Exception:
                pass
        self.Session = sessionmaker(bind=self.engine)

        self._patcher = patch("services.note_service.write_to_vault", return_value=False)
        self._patcher.start()

    def tearDown(self) -> None:
        self._patcher.stop()
        self.engine.dispose()

    def _create_note(self, db, title="Test Note", source_path="/vault/test.md") -> Note:
        note = Note(title=title, content="content", source="obsidian", source_path=source_path)
        db.add(note)
        db.flush()
        return note


class TestDetectConflict(SyncServiceTestBase):
    def test_no_conflict_when_both_none(self) -> None:
        self.assertFalse(detect_conflict(None, None))

    def test_no_conflict_when_local_none(self) -> None:
        remote = datetime.now(timezone.utc)
        self.assertFalse(detect_conflict(None, remote))

    def test_no_conflict_when_remote_none(self) -> None:
        local = datetime.now(timezone.utc)
        self.assertFalse(detect_conflict(local, None))

    def test_no_conflict_when_mtimes_close(self) -> None:
        now = datetime.now(timezone.utc)
        local = now
        remote = now + timedelta(seconds=1)
        self.assertFalse(detect_conflict(local, remote))

    def test_conflict_when_mtimes_differ(self) -> None:
        local = datetime(2024, 1, 1, tzinfo=timezone.utc)
        remote = datetime(2024, 1, 2, tzinfo=timezone.utc)
        self.assertTrue(detect_conflict(local, remote))

    def test_conflict_at_tolerance_boundary(self) -> None:
        now = datetime.now(timezone.utc)
        local = now
        remote = now + timedelta(seconds=CONFLICT_TOLERANCE_SECONDS + 1)
        self.assertTrue(detect_conflict(local, remote))

    def test_no_conflict_within_tolerance(self) -> None:
        now = datetime.now(timezone.utc)
        local = now
        remote = now + timedelta(seconds=CONFLICT_TOLERANCE_SECONDS)
        self.assertFalse(detect_conflict(local, remote))

    def test_handles_naive_datetimes(self) -> None:
        local = datetime(2024, 1, 1)
        remote = datetime(2024, 1, 2)
        self.assertTrue(detect_conflict(local, remote))


class TestListConflicts(SyncServiceTestBase):
    def test_empty_when_no_conflicts(self) -> None:
        with self.Session() as db:
            self._create_note(db)
            db.commit()
            result = list_conflicts(db)
            self.assertEqual(result, [])

    def test_lists_only_conflicted_notes(self) -> None:
        with self.Session() as db:
            note1 = self._create_note(db, "Note 1", "/vault/n1.md")
            note2 = self._create_note(db, "Note 2", "/vault/n2.md")
            db.flush()

            sync1 = SyncState(note_id=note1.id, conflict=False)
            sync2 = SyncState(
                note_id=note2.id,
                conflict=True,
                local_mtime=datetime(2024, 1, 1, tzinfo=timezone.utc),
                remote_mtime=datetime(2024, 1, 2, tzinfo=timezone.utc),
            )
            db.add_all([sync1, sync2])
            db.commit()

            result = list_conflicts(db)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["note_id"], note2.id)
            self.assertEqual(result[0]["title"], "Note 2")
            self.assertEqual(result[0]["source_path"], "/vault/n2.md")

    def test_includes_mtime_info(self) -> None:
        with self.Session() as db:
            note = self._create_note(db, "Note", "/vault/n.md")
            db.flush()
            sync = SyncState(
                note_id=note.id,
                conflict=True,
                local_mtime=datetime(2024, 1, 1, tzinfo=timezone.utc),
                remote_mtime=datetime(2024, 1, 2, tzinfo=timezone.utc),
            )
            db.add(sync)
            db.commit()

            result = list_conflicts(db)
            self.assertIsNotNone(result[0]["local_mtime"])
            self.assertIsNotNone(result[0]["remote_mtime"])


class TestResolveConflict(SyncServiceTestBase):
    def test_keep_local_clears_conflict(self) -> None:
        with self.Session() as db:
            note = self._create_note(db, "Conflict Note", "/vault/conflict.md")
            db.flush()
            sync = SyncState(
                note_id=note.id,
                conflict=True,
                local_mtime=datetime(2024, 1, 1, tzinfo=timezone.utc),
                remote_mtime=datetime(2024, 1, 2, tzinfo=timezone.utc),
            )
            db.add(sync)
            db.commit()

            result = resolve_conflict(db, note.id, "keep_local")
            self.assertEqual(result["status"], "ok")

            db.refresh(sync)
            self.assertFalse(sync.conflict)

    def test_keep_remote_reads_vault_file(self) -> None:
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, dir="/tmp") as f:
            f.write("remote content from vault")
            vault_path = f.name

        try:
            with self.Session() as db:
                note = Note(
                    title="Remote Note",
                    content="local content",
                    source="obsidian",
                    source_path=vault_path,
                )
                db.add(note)
                db.flush()
                sync = SyncState(
                    note_id=note.id,
                    conflict=True,
                    local_mtime=datetime(2024, 1, 1, tzinfo=timezone.utc),
                    remote_mtime=datetime(2024, 1, 2, tzinfo=timezone.utc),
                )
                db.add(sync)
                db.commit()

                with patch("services.sync_service.settings.obsidian_vault_path", "/tmp"):
                    result = resolve_conflict(db, note.id, "keep_remote")

                self.assertEqual(result["status"], "ok")
                db.refresh(note)
                self.assertEqual(note.content, "remote content from vault")
                db.refresh(sync)
                self.assertFalse(sync.conflict)
        finally:
            os.unlink(vault_path)

    def test_merge_updates_content(self) -> None:
        with self.Session() as db:
            note = self._create_note(db, "Merge Note", "/vault/merge.md")
            note.content = "original"
            db.flush()
            sync = SyncState(
                note_id=note.id,
                conflict=True,
                local_mtime=datetime(2024, 1, 1, tzinfo=timezone.utc),
                remote_mtime=datetime(2024, 1, 2, tzinfo=timezone.utc),
            )
            db.add(sync)
            db.commit()

            result = resolve_conflict(db, note.id, "merge", merged_content="merged content")
            self.assertEqual(result["status"], "ok")

            db.refresh(note)
            self.assertEqual(note.content, "merged content")
            db.refresh(sync)
            self.assertFalse(sync.conflict)

    def test_merge_without_content_returns_error(self) -> None:
        with self.Session() as db:
            note = self._create_note(db, "Merge Note", "/vault/merge.md")
            db.flush()
            sync = SyncState(note_id=note.id, conflict=True)
            db.add(sync)
            db.commit()

            result = resolve_conflict(db, note.id, "merge", merged_content=None)
            self.assertEqual(result["status"], "error")

    def test_resolve_nonexistent_note_returns_error(self) -> None:
        with self.Session() as db:
            result = resolve_conflict(db, 99999, "keep_local")
            self.assertEqual(result["status"], "error")

    def test_resolve_no_conflict_returns_ok(self) -> None:
        with self.Session() as db:
            note = self._create_note(db, "No Conflict", "/vault/noconflict.md")
            db.flush()
            sync = SyncState(note_id=note.id, conflict=False)
            db.add(sync)
            db.commit()

            result = resolve_conflict(db, note.id, "keep_local")
            self.assertEqual(result["status"], "ok")


class TestUpdateLocalMtime(SyncServiceTestBase):
    def test_creates_sync_state_if_missing(self) -> None:
        with self.Session() as db:
            note = self._create_note(db)
            db.commit()

            update_local_mtime(db, note.id)
            db.commit()

            sync = db.query(SyncState).filter(SyncState.note_id == note.id).first()
            self.assertIsNotNone(sync)
            self.assertIsNotNone(sync.local_mtime)

    def test_updates_existing_sync_state(self) -> None:
        with self.Session() as db:
            note = self._create_note(db)
            db.flush()
            old_time = datetime(2020, 1, 1, tzinfo=timezone.utc)
            sync = SyncState(note_id=note.id, local_mtime=old_time)
            db.add(sync)
            db.commit()

            update_local_mtime(db, note.id)
            db.commit()

            db.refresh(sync)
            self.assertNotEqual(sync.local_mtime, old_time)


if __name__ == "__main__":
    unittest.main()
