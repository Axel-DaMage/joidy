"""Unit tests for note_service — core note CRUD and tag/link sync logic."""

import os
import sys
import types
import tempfile
import unittest

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Stub sqlite_vec before importing any app modules
if "sqlite_vec" not in sys.modules:
    _stub = types.ModuleType("sqlite_vec")
    _stub.load = lambda _conn: None  # type: ignore
    sys.modules["sqlite_vec"] = _stub

from database import Base
from models.note import Note, NoteTag, NoteLink, Tag, TagCooccurrence, EmbeddingFailure
from models.gamification import UserStats, XPEvent, StreakRecord
from models.skill import Skill
from services.note_service import (
    create_note,
    update_note,
    delete_note,
    get_or_create_tag,
    note_to_response,
    sync_note_links,
    list_backlinks,
)


class NoteServiceTestBase(unittest.TestCase):
    """Base class with in-memory SQLite setup."""

    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        # Create tag_cooccurrences table (used by tag_graph service)
        with self.engine.begin() as conn:
            try:
                conn.execute(text(
                    "CREATE TABLE IF NOT EXISTS tag_cooccurrences "
                    "(tag_a_id INTEGER, tag_b_id INTEGER, weight INTEGER, "
                    "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
                ))
            except Exception:
                pass  # Table may already exist via Base.metadata
        self.Session = sessionmaker(bind=self.engine)

    def tearDown(self) -> None:
        self.engine.dispose()


class TestGetOrCreateTag(NoteServiceTestBase):
    def test_creates_new_tag(self) -> None:
        with self.Session() as db:
            tag = get_or_create_tag(db, "python")
            db.commit()
            self.assertEqual(tag.name, "python")
            self.assertIsNotNone(tag.id)

    def test_returns_existing_tag(self) -> None:
        with self.Session() as db:
            tag1 = get_or_create_tag(db, "python")
            db.commit()
            tag2 = get_or_create_tag(db, "Python")  # Different case
            self.assertEqual(tag1.id, tag2.id)

    def test_normalizes_whitespace(self) -> None:
        with self.Session() as db:
            tag = get_or_create_tag(db, "  machine learning  ")
            db.commit()
            self.assertEqual(tag.name, "machine learning")


class TestNoteToResponse(NoteServiceTestBase):
    def test_serializes_note_with_tags(self) -> None:
        with self.Session() as db:
            note = Note(title="Test", content="Body", source="joidy")
            db.add(note)
            db.flush()
            tag = get_or_create_tag(db, "test-tag")
            db.add(NoteTag(note_id=note.id, tag_id=tag.id, source="manual"))
            db.commit()
            db.refresh(note)

            resp = note_to_response(note)
            self.assertEqual(resp["title"], "Test")
            self.assertEqual(resp["tags"], ["test-tag"])
            self.assertIn("created_at", resp)
            self.assertIn("updated_at", resp)


class TestCreateNote(NoteServiceTestBase):
    def test_creates_note_with_tags(self) -> None:
        with self.Session() as db:
            note, gami = create_note(
                db,
                title="My Note",
                content="Hello world",
                tags=["python", "tutorial"],
                source="joidy",
                source_path=None,
                rebuild_derived_data=False,
            )
            self.assertIsNotNone(note.id)
            self.assertEqual(note.title, "My Note")
            self.assertEqual(len(note.tags), 2)
            self.assertIsNotNone(gami)

    def test_create_note_strips_empty_tags(self) -> None:
        with self.Session() as db:
            note, _ = create_note(
                db,
                title="Tag Test",
                content="Content",
                tags=["valid", "", "  ", "also-valid"],
                source="joidy",
                source_path=None,
                rebuild_derived_data=False,
            )
            tag_names = sorted([nt.tag.name for nt in note.tags])
            self.assertIn("valid", tag_names)
            self.assertIn("also-valid", tag_names)
            self.assertEqual(len(tag_names), 2)

    def test_create_note_sanitizes_title(self) -> None:
        with self.Session() as db:
            note, _ = create_note(
                db,
                title="Test <script>alert('xss')</script> Note",
                content="Safe content",
                tags=[],
                source="joidy",
                source_path=None,
                rebuild_derived_data=False,
            )
            self.assertNotIn("<script>", note.title)


class TestUpdateNote(NoteServiceTestBase):
    def test_updates_title_and_content(self) -> None:
        with self.Session() as db:
            note, _ = create_note(
                db, title="Original", content="Old " * 50,
                tags=[], source="joidy", source_path=None,
                rebuild_derived_data=False,
            )
            updated, gami = update_note(
                db, note.id,
                title="Updated Title",
                content="New " * 50,
                rebuild_derived_data=False,
            )
            self.assertEqual(updated.title, "Updated Title")
            self.assertIsNotNone(gami)

    def test_update_returns_none_for_missing_note(self) -> None:
        with self.Session() as db:
            note, gami = update_note(db, 99999, title="X", rebuild_derived_data=False)
            self.assertIsNone(note)
            self.assertIsNone(gami)

    def test_update_replaces_tags(self) -> None:
        with self.Session() as db:
            note, _ = create_note(
                db, title="Tags", content="C",
                tags=["old-tag"], source="joidy", source_path=None,
                rebuild_derived_data=False,
            )
            updated, _ = update_note(
                db, note.id, tags=["new-tag-a", "new-tag-b"],
                rebuild_derived_data=False,
            )
            tag_names = sorted([nt.tag.name for nt in updated.tags])
            self.assertEqual(tag_names, ["new-tag-a", "new-tag-b"])


class TestDeleteNote(NoteServiceTestBase):
    def test_deletes_existing_note(self) -> None:
        with self.Session() as db:
            note, _ = create_note(
                db, title="Delete Me", content="X",
                tags=["removable"], source="joidy", source_path=None,
                rebuild_derived_data=False,
            )
            result = delete_note(db, note.id)
            self.assertTrue(result)
            self.assertIsNone(db.query(Note).filter(Note.id == note.id).first())

    def test_delete_returns_false_for_missing(self) -> None:
        with self.Session() as db:
            self.assertFalse(delete_note(db, 99999))


class TestSyncNoteLinks(NoteServiceTestBase):
    def test_parses_wikilinks(self) -> None:
        with self.Session() as db:
            target = Note(title="Target Note", content="", source="joidy")
            db.add(target)
            source = Note(title="Source", content="See [[Target Note]]", source="joidy")
            db.add(source)
            db.flush()

            sync_note_links(db, source.id, source.content)
            db.commit()

            links = db.query(NoteLink).filter(NoteLink.source_note_id == source.id).all()
            self.assertEqual(len(links), 1)
            self.assertEqual(links[0].target_note_id, target.id)

    def test_wikilinks_with_alias(self) -> None:
        with self.Session() as db:
            target = Note(title="My Note", content="", source="joidy")
            db.add(target)
            source = Note(title="Source", content="See [[My Note|alias]]", source="joidy")
            db.add(source)
            db.flush()

            sync_note_links(db, source.id, source.content)
            db.commit()

            links = db.query(NoteLink).filter(NoteLink.source_note_id == source.id).all()
            self.assertEqual(len(links), 1)


class TestListBacklinks(NoteServiceTestBase):
    def test_returns_notes_linking_to_target(self) -> None:
        with self.Session() as db:
            target = Note(title="Target", content="", source="joidy")
            source1 = Note(title="Source1", content="[[Target]]", source="joidy")
            source2 = Note(title="Source2", content="[[Target]]", source="joidy")
            db.add_all([target, source1, source2])
            db.flush()

            sync_note_links(db, source1.id, source1.content)
            sync_note_links(db, source2.id, source2.content)
            db.commit()

            backlinks = list_backlinks(db, target.id)
            self.assertEqual(len(backlinks), 2)
            titles = sorted([n.title for n in backlinks])
            self.assertEqual(titles, ["Source1", "Source2"])


if __name__ == "__main__":
    unittest.main()
