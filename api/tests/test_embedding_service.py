"""Unit tests for embedding_service — retry logic, dead letter queue, failure tracking."""

import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

# Stub sqlite_vec before importing any app modules
if "sqlite_vec" not in sys.modules:
    _stub = types.ModuleType("sqlite_vec")
    _stub.load = lambda _conn: None  # type: ignore
    sys.modules["sqlite_vec"] = _stub

from database import Base
from models.note import EmbeddingFailure, Note
from services.embedding_service import (
    get_dead_letter_entries,
    get_retryable_embedding_notes,
    purge_dead_letters,
    reset_dead_letter_entry,
)


class EmbeddingServiceTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def tearDown(self) -> None:
        self.engine.dispose()


class TestGetRetryableNotes(EmbeddingServiceTestBase):
    def test_returns_notes_below_max_attempts(self) -> None:
        with self.Session() as db:
            note = Note(title="Test", content="Body", source="joidy")
            db.add(note)
            db.flush()

            failure = EmbeddingFailure(
                note_id=note.id, attempts=2,
                last_error="timeout",
                next_retry_at=datetime.now(timezone.utc) - timedelta(seconds=1),
            )
            db.add(failure)
            db.commit()

            notes = get_retryable_embedding_notes(db, limit=10)
            self.assertEqual(len(notes), 1)
            self.assertEqual(notes[0].id, note.id)

    def test_excludes_dead_lettered_entries(self) -> None:
        with self.Session() as db:
            note = Note(title="Dead", content="Body", source="joidy")
            db.add(note)
            db.flush()

            failure = EmbeddingFailure(
                note_id=note.id, attempts=10,  # >= max_attempts (8)
                last_error="permanent failure",
                next_retry_at=None,
            )
            db.add(failure)
            db.commit()

            notes = get_retryable_embedding_notes(db, limit=10)
            self.assertEqual(len(notes), 0)

    def test_excludes_future_retries(self) -> None:
        with self.Session() as db:
            note = Note(title="Future", content="Body", source="joidy")
            db.add(note)
            db.flush()

            failure = EmbeddingFailure(
                note_id=note.id, attempts=1,
                last_error="temp",
                next_retry_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )
            db.add(failure)
            db.commit()

            notes = get_retryable_embedding_notes(db, limit=10)
            self.assertEqual(len(notes), 0)

    def test_cleans_orphaned_failures(self) -> None:
        with self.Session() as db:
            # Failure without a matching note
            failure = EmbeddingFailure(
                note_id=99999, attempts=1,
                last_error="orphan",
                next_retry_at=datetime.now(timezone.utc) - timedelta(seconds=1),
            )
            db.add(failure)
            db.commit()

            notes = get_retryable_embedding_notes(db, limit=10)
            self.assertEqual(len(notes), 0)
            # Orphaned failure should be cleaned up
            remaining = db.query(EmbeddingFailure).filter(EmbeddingFailure.note_id == 99999).first()
            self.assertIsNone(remaining)

    def test_o1_select_queries_with_multiple_failures(self) -> None:
        """Regression test for N+1 query loop (#997): SELECT query count is O(1) regardless of N."""
        with self.Session() as db:
            notes = []
            now = datetime.now(timezone.utc)
            for i in range(10):
                note = Note(title=f"Note {i}", content=f"Body {i}", source="joidy")
                db.add(note)
                notes.append(note)
            db.flush()

            for i, note in enumerate(notes):
                failure = EmbeddingFailure(
                    note_id=note.id,
                    attempts=1,
                    last_error="temp",
                    next_retry_at=now - timedelta(seconds=10 - i),
                    updated_at=now - timedelta(seconds=10 - i),
                )
                db.add(failure)
            db.commit()

            select_queries = []

            def capture_select(conn, cursor, statement, parameters, context, executemany):
                if statement.strip().upper().startswith("SELECT"):
                    select_queries.append(statement)

            event.listen(self.engine, "before_cursor_execute", capture_select)
            try:
                result_notes = get_retryable_embedding_notes(db, limit=20)
            finally:
                event.remove(self.engine, "before_cursor_execute", capture_select)

            self.assertEqual(len(result_notes), 10)
            # Exactly 2 SELECTs: 1 for embedding_failures, 1 for notes IN (...)
            self.assertEqual(len(select_queries), 2)
            # Preserves order of failures (ordered by updated_at asc)
            self.assertEqual([n.id for n in result_notes], [n.id for n in notes])

    def test_mixed_valid_and_orphaned_failures_query_count_and_cleanup(self) -> None:
        """Handles mix of valid and orphaned failure records with O(1) SELECTs."""
        with self.Session() as db:
            now = datetime.now(timezone.utc)
            valid_notes = []
            for i in range(3):
                note = Note(title=f"Valid {i}", content=f"Content {i}", source="joidy")
                db.add(note)
                valid_notes.append(note)
            db.flush()

            for note in valid_notes:
                db.add(EmbeddingFailure(
                    note_id=note.id, attempts=1, last_error="err",
                    next_retry_at=now - timedelta(seconds=1),
                ))
            # Add 2 orphaned failures
            for orphan_id in [88888, 99999]:
                db.add(EmbeddingFailure(
                    note_id=orphan_id, attempts=1, last_error="orphan",
                    next_retry_at=now - timedelta(seconds=1),
                ))
            db.commit()

            select_queries = []
            event.listen(self.engine, "before_cursor_execute", lambda conn, cursor, stmt, *_: select_queries.append(stmt) if stmt.strip().upper().startswith("SELECT") else None)

            result = get_retryable_embedding_notes(db, limit=20)
            self.assertEqual(len(result), 3)
            self.assertEqual([n.id for n in result], [n.id for n in valid_notes])
            # Exactly 2 SELECT queries
            self.assertEqual(len(select_queries), 2)
            # Orphaned failures marked for deletion in session
            self.assertEqual(len(db.deleted), 2)


class TestDeadLetterQueue(EmbeddingServiceTestBase):
    def test_get_dead_letter_entries(self) -> None:
        with self.Session() as db:
            note = Note(title="DLQ", content="X", source="joidy")
            db.add(note)
            db.flush()

            failure = EmbeddingFailure(
                note_id=note.id, attempts=10,
                last_error="Permanent: API key invalid",
                next_retry_at=None,
            )
            db.add(failure)
            db.commit()

            entries = get_dead_letter_entries(db, limit=50)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["note_id"], note.id)
            self.assertEqual(entries[0]["attempts"], 10)

    def test_reset_dead_letter_entry(self) -> None:
        with self.Session() as db:
            note = Note(title="Reset", content="X", source="joidy")
            db.add(note)
            db.flush()

            failure = EmbeddingFailure(
                note_id=note.id, attempts=10,
                last_error="error",
                next_retry_at=None,
            )
            db.add(failure)
            db.commit()

            result = reset_dead_letter_entry(db, note.id)
            self.assertTrue(result)

            db.refresh(failure)
            self.assertEqual(failure.attempts, 0)
            self.assertIsNotNone(failure.next_retry_at)

    def test_reset_returns_false_for_missing(self) -> None:
        with self.Session() as db:
            self.assertFalse(reset_dead_letter_entry(db, 99999))

    def test_purge_dead_letters(self) -> None:
        with self.Session() as db:
            note = Note(title="Purge", content="X", source="joidy")
            db.add(note)
            db.flush()

            db.add(EmbeddingFailure(note_id=note.id, attempts=10, last_error="e"))
            db.commit()

            count = purge_dead_letters(db)
            self.assertEqual(count, 1)
            self.assertEqual(db.query(EmbeddingFailure).count(), 0)


class TestClearEmbeddingFailure(EmbeddingServiceTestBase):
    @patch("services.embedding_service.SessionLocal")
    def test_clear_removes_failure(self, mock_session_cls) -> None:
        with self.Session() as db:
            note = Note(title="Clear", content="X", source="joidy")
            db.add(note)
            db.flush()

            failure = EmbeddingFailure(note_id=note.id, attempts=3, last_error="err")
            db.add(failure)
            db.commit()

            # Directly test via session
            db.query(EmbeddingFailure).filter(EmbeddingFailure.note_id == note.id).delete()
            db.commit()

            remaining = db.query(EmbeddingFailure).filter(EmbeddingFailure.note_id == note.id).first()
            self.assertIsNone(remaining)


if __name__ == "__main__":
    unittest.main()
