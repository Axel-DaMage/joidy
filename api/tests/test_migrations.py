"""Tests for the Alembic migration serialization logic (#816).

Verifies that ``_run_migrations`` takes a PostgreSQL advisory lock around
``alembic upgrade head`` so concurrent uvicorn workers serialize instead of
racing on cold start. The lock path is exercised via mocking so the test
runs without modifying the live database.
"""

import logging
import sys
import types
import unittest
from unittest import mock

from alembic.util.exc import CommandError

# Stub sqlite_vec before importing app modules (matches conftest pattern).
if "sqlite_vec" not in sys.modules:
    _stub = types.ModuleType("sqlite_vec")
    _stub.load = lambda _conn: None  # type: ignore
    sys.modules["sqlite_vec"] = _stub

from database import (
    _ALEMBIC_ADVISORY_LOCK_KEY,
    _missing_revision_id,
    _run_migrations,
)


class _FakeDialect:
    def __init__(self, name: str):
        self.name = name


class _FakeConnection:
    """Records executed statements in order so tests can assert lock/unlock
    sequencing around the migration call."""

    def __init__(self, recorder: list):
        self._recorder = recorder

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, stmt, params=None):
        # Capture the advisory-lock SQL by stringifying the text() clause.
        self._recorder.append((str(stmt), params))

    def commit(self):
        self._recorder.append(("commit", None))


class _FakeEngine:
    def __init__(self, dialect_name: str, recorder: list):
        self.dialect = _FakeDialect(dialect_name)
        self._recorder = recorder

    def connect(self):
        return _FakeConnection(self._recorder)


class RunMigrationsTest(unittest.TestCase):
    def test_advisory_lock_taken_and_released_on_postgresql(self):
        recorder: list = []
        fake_engine = _FakeEngine("postgresql", recorder)

        with (
            mock.patch("database.engine", fake_engine),
            mock.patch("database.command.upgrade") as upgrade_mock,
        ):
            _run_migrations()

        upgrade_mock.assert_called_once()
        # Expect: lock, unlock, commit (in that order).
        self.assertEqual(len(recorder), 3)
        lock_sql, lock_params = recorder[0]
        unlock_sql, unlock_params = recorder[1]
        commit_marker = recorder[2]
        self.assertIn("pg_advisory_lock", lock_sql)
        self.assertEqual(lock_params, {"key": _ALEMBIC_ADVISORY_LOCK_KEY})
        self.assertIn("pg_advisory_unlock", unlock_sql)
        self.assertEqual(unlock_params, {"key": _ALEMBIC_ADVISORY_LOCK_KEY})
        self.assertEqual(commit_marker, ("commit", None))

    def test_no_advisory_lock_on_non_postgresql(self):
        recorder: list = []
        fake_engine = _FakeEngine("sqlite", recorder)

        with (
            mock.patch("database.engine", fake_engine),
            mock.patch("database.command.upgrade") as upgrade_mock,
        ):
            _run_migrations()

        upgrade_mock.assert_called_once()
        # No lock/unlock statements should have been issued.
        self.assertEqual(recorder, [])

    def test_advisory_lock_released_even_if_upgrade_raises(self):
        recorder: list = []
        fake_engine = _FakeEngine("postgresql", recorder)

        with (
            mock.patch("database.engine", fake_engine),
            mock.patch(
                "database.command.upgrade",
                side_effect=RuntimeError("boom"),
            ),
            self.assertRaises(RuntimeError),
        ):
            _run_migrations()

        # Lock must still be released and committed even on failure —
        # otherwise a crashed migration would wedge every other worker.
        self.assertEqual(len(recorder), 3)
        self.assertIn("pg_advisory_unlock", recorder[1][0])
        self.assertEqual(recorder[2], ("commit", None))


class MissingRevisionDetectionTest(unittest.TestCase):
    """Coverage for the "DB migrated by a newer Joidy version" crash path —
    ``alembic_version`` names a revision absent from the running code (#1489)."""

    def test_cant_locate_revision_logs_critical_and_reraises(self):
        recorder: list = []
        fake_engine = _FakeEngine("sqlite", recorder)

        with (
            mock.patch("database.engine", fake_engine),
            mock.patch(
                "database.command.upgrade",
                side_effect=CommandError("Can't locate revision identified by 'b4c5d6e7f8a9'"),
            ),
            self.assertLogs("database", level="CRITICAL") as logs,
            self.assertRaises(CommandError),
        ):
            _run_migrations()

        output = "\n".join(logs.output)
        self.assertIn("b4c5d6e7f8a9", output)
        self.assertIn("NEWER Joidy version", output)
        self.assertIn("OLDER", output)
        self.assertIn("update to a newer Joidy image", output)
        self.assertIn("downgrade", output)

    def test_missing_revision_id_extraction(self):
        cases = [
            (CommandError("Can't locate revision identified by 'b4c5d6e7f8a9'"), "b4c5d6e7f8a9"),
            (CommandError("Can't locate revision identified by '0001_initial'"), "0001_initial"),
            # Non-CommandError type carrying the same message (other alembic
            # versions may raise differently) still extracts via message match.
            (RuntimeError("Can't locate revision identified by 'deadbeef00'"), "deadbeef00"),
            (CommandError("some other alembic failure"), None),
            (RuntimeError("unrelated"), None),
        ]
        for exc, expected in cases:
            with self.subTest(exc=exc):
                self.assertEqual(_missing_revision_id(exc), expected)

    def test_other_exceptions_take_generic_path(self):
        recorder: list = []
        fake_engine = _FakeEngine("sqlite", recorder)

        with (
            mock.patch("database.engine", fake_engine),
            mock.patch(
                "database.command.upgrade",
                side_effect=RuntimeError("boom"),
            ),
            self.assertLogs("database", level="ERROR") as logs,
            self.assertRaises(RuntimeError),
        ):
            _run_migrations()

        output = "\n".join(logs.output)
        self.assertIn("Failed to apply database migrations", output)
        self.assertNotIn("NEWER Joidy version", output)
        # No CRITICAL "ahead of code" record was emitted.
        for record in logs.records:
            self.assertLess(record.levelno, logging.CRITICAL)

    def test_non_matching_command_error_takes_generic_path(self):
        recorder: list = []
        fake_engine = _FakeEngine("sqlite", recorder)

        with (
            mock.patch("database.engine", fake_engine),
            mock.patch(
                "database.command.upgrade",
                side_effect=CommandError("Target database is not up to date."),
            ),
            self.assertLogs("database", level="ERROR") as logs,
            self.assertRaises(CommandError),
        ):
            _run_migrations()

        output = "\n".join(logs.output)
        self.assertIn("Failed to apply database migrations", output)
        self.assertNotIn("NEWER Joidy version", output)


if __name__ == "__main__":
    unittest.main()
