"""Unit tests for webhook_sync service — create/update/delete event processing."""

import sys
import types
import unittest
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
from services.webhook_sync import (
    _extract_tags,
    _find_note_by_path,
    _parse_frontmatter,
    _title_from_path,
    process_webhook_event,
)


class WebhookSyncTestBase(unittest.TestCase):
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

        # Patch write_to_vault so tests don't touch the filesystem
        self._patcher = patch("services.note_service.write_to_vault", return_value=False)
        self._patcher.start()

    def tearDown(self) -> None:
        self._patcher.stop()
        self.engine.dispose()


class TestParseFrontmatter(WebhookSyncTestBase):
    def test_extracts_title_and_body(self) -> None:
        content = "---\ntitle: My Note\ntags: [python, web]\n---\n# Body text"
        fm, body = _parse_frontmatter(content)
        self.assertEqual(fm["title"], "My Note")
        self.assertEqual(fm["tags"], "[python, web]")
        self.assertEqual(body, "# Body text")

    def test_no_frontmatter(self) -> None:
        content = "Just plain text"
        fm, body = _parse_frontmatter(content)
        self.assertEqual(fm, {})
        self.assertEqual(body, "Just plain text")


class TestExtractTags(WebhookSyncTestBase):
    def test_frontmatter_and_inline(self) -> None:
        content = "---\ntags: [python, web]\n---\n#python is great #too"
        fm, _ = _parse_frontmatter(content)
        tags = _extract_tags(content, fm)
        self.assertIn("python", tags)
        self.assertIn("web", tags)
        self.assertIn("too", tags)

    def test_no_tags(self) -> None:
        tags = _extract_tags("no tags here", {})
        self.assertEqual(tags, [])


class TestTitleFromPath(WebhookSyncTestBase):
    def test_simple_path(self) -> None:
        self.assertEqual(_title_from_path("/vault/my-note.md"), "My Note")

    def test_nested_path(self) -> None:
        self.assertEqual(_title_from_path("/vault/folder/another_note.md"), "Another Note")


class TestProcessWebhookCreate(WebhookSyncTestBase):
    def test_create_new_note(self) -> None:
        with self.Session() as db:
            result = process_webhook_event(
                db,
                event="create",
                path="/vault/test-note.md",
                content="# Test Note\n\nHello world",
                source="obsidian",
            )
            db.commit()

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["action"], "created")
        self.assertIsNotNone(result["note_id"])

        with self.Session() as db:
            note = db.query(Note).filter(Note.source_path == "/vault/test-note.md").first()
            self.assertIsNotNone(note)
            self.assertEqual(note.source, "obsidian")

    def test_create_with_frontmatter_title(self) -> None:
        content = "---\ntitle: Custom Title\ntags: [python]\n---\nBody"
        with self.Session() as db:
            result = process_webhook_event(
                db,
                event="create",
                path="/vault/note.md",
                content=content,
                source="obsidian",
            )
            db.commit()

        with self.Session() as db:
            note = db.query(Note).filter(Note.source_path == "/vault/note.md").first()
            self.assertIsNotNone(note)
            self.assertEqual(note.title, "Custom Title")

    def test_create_extracts_tags(self) -> None:
        content = "---\ntags: [python, web]\n---\n#python is great"
        with self.Session() as db:
            result = process_webhook_event(
                db,
                event="create",
                path="/vault/tagged.md",
                content=content,
                source="obsidian",
            )
            db.commit()

        with self.Session() as db:
            note = db.query(Note).filter(Note.source_path == "/vault/tagged.md").first()
            tag_names = {nt.tag.name for nt in note.tags}
            self.assertIn("python", tag_names)
            self.assertIn("web", tag_names)

    def test_create_sets_sync_state(self) -> None:
        with self.Session() as db:
            result = process_webhook_event(
                db,
                event="create",
                path="/vault/synced.md",
                content="content",
                mtime=1700000000,
                source="obsidian",
            )
            db.commit()

        with self.Session() as db:
            sync = db.query(SyncState).filter(SyncState.note_id == result["note_id"]).first()
            self.assertIsNotNone(sync)
            self.assertIsNotNone(sync.remote_mtime)
            self.assertFalse(sync.conflict)


class TestProcessWebhookUpdate(WebhookSyncTestBase):
    def test_update_existing_note(self) -> None:
        with self.Session() as db:
            process_webhook_event(
                db,
                event="create",
                path="/vault/update.md",
                content="original content",
                source="obsidian",
            )
            db.commit()

        with self.Session() as db:
            result = process_webhook_event(
                db,
                event="update",
                path="/vault/update.md",
                content="updated content",
                source="obsidian",
            )
            db.commit()

        self.assertEqual(result["action"], "updated")

        with self.Session() as db:
            note = db.query(Note).filter(Note.source_path == "/vault/update.md").first()
            self.assertEqual(note.content, "updated content")

    def test_update_creates_if_not_found(self) -> None:
        with self.Session() as db:
            result = process_webhook_event(
                db,
                event="update",
                path="/vault/missing.md",
                content="content for missing note",
                source="obsidian",
            )
            db.commit()

        self.assertEqual(result["action"], "created")


class TestProcessWebhookDelete(WebhookSyncTestBase):
    def test_delete_existing_note(self) -> None:
        with self.Session() as db:
            create_result = process_webhook_event(
                db,
                event="create",
                path="/vault/delete-me.md",
                content="to be deleted",
                source="obsidian",
            )
            db.commit()
            note_id = create_result["note_id"]

        with self.Session() as db:
            result = process_webhook_event(
                db,
                event="delete",
                path="/vault/delete-me.md",
                source="obsidian",
            )
            db.commit()

        self.assertEqual(result["action"], "deleted")
        self.assertEqual(result["note_id"], note_id)

        with self.Session() as db:
            note = db.query(Note).filter(Note.id == note_id).first()
            self.assertIsNone(note)

    def test_delete_unknown_path_is_noop(self) -> None:
        with self.Session() as db:
            result = process_webhook_event(
                db,
                event="delete",
                path="/vault/nonexistent.md",
                source="obsidian",
            )
            db.commit()

        self.assertEqual(result["action"], "noop")
        self.assertIsNone(result["note_id"])


class TestProcessWebhookValidation(WebhookSyncTestBase):
    def test_invalid_event_raises(self) -> None:
        with self.Session() as db:
            with self.assertRaises(ValueError):
                process_webhook_event(
                    db,
                    event="invalid",
                    path="/vault/note.md",
                    content="content",
                    source="obsidian",
                )

    def test_create_without_content_raises(self) -> None:
        with self.Session() as db:
            with self.assertRaises(ValueError):
                process_webhook_event(
                    db,
                    event="create",
                    path="/vault/note.md",
                    content=None,
                    source="obsidian",
                )

    def test_update_without_content_raises(self) -> None:
        with self.Session() as db:
            with self.assertRaises(ValueError):
                process_webhook_event(
                    db,
                    event="update",
                    path="/vault/note.md",
                    content=None,
                    source="obsidian",
                )


if __name__ == "__main__":
    unittest.main()
