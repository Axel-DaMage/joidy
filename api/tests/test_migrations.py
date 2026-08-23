"""Tests for the Alembic migration serialization logic (#816).

Verifies that ``_run_migrations`` takes a PostgreSQL advisory lock around
``alembic upgrade head`` so concurrent uvicorn workers serialize instead of
racing on cold start. The lock path is exercised via mocking so the test
runs without modifying the live database.
"""

import sys
import types
import unittest
from unittest import mock

# Stub sqlite_vec before importing app modules (matches conftest pattern).
if "sqlite_vec" not in sys.modules:
    _stub = types.ModuleType("sqlite_vec")
    _stub.load = lambda _conn: None  # type: ignore
    sys.modules["sqlite_vec"] = _stub

from database import _ALEMBIC_ADVISORY_LOCK_KEY, _run_migrations


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


if __name__ == "__main__":
    unittest.main()
