"""Tests for real-time vault sync broadcasting via WebSocket (#73).

Covers:
- Creating a note with source="obsidian" triggers a `vault_synced` broadcast.
- Updating a note from the vault triggers a `vault_synced` broadcast.
- Creating a note with a non-obsidian source does NOT trigger `vault_synced`.
- The ``GET /sync/status`` endpoint returns last_sync_time, pending_conflicts,
  and total_synced.
"""

import sys
import types
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

if "sqlite_vec" not in sys.modules:
    _stub = types.ModuleType("sqlite_vec")
    _stub.load = lambda _conn: None  # type: ignore
    sys.modules["sqlite_vec"] = _stub

from database import Base, get_db
import main as main_module
from main import app
from middleware.rate_limit import _default_limiter
from models.note import Note
from models.sync_state import SyncState
from services.auth_service import get_current_user

# Prevent lifespan migrations during tests.
main_module.init_db = lambda: None


def _build_client(db_session):
    """Build a TestClient wired to an isolated DB session."""

    def override_get_db():
        yield db_session

    def override_get_current_user():
        return 1

    original_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    client = TestClient(app)
    client._original_overrides = original_overrides  # type: ignore[attr-defined]
    return client


def _teardown_client(client):
    app.dependency_overrides.clear()
    app.dependency_overrides.update(client._original_overrides)  # type: ignore[attr-defined]


class VaultSyncBroadcastTestBase(unittest.TestCase):
    """Base class with in-memory SQLite + write_to_vault patched out."""

    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
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

        self._vault_patcher = patch("services.note_service.write_to_vault", return_value=False)
        self._vault_patcher.start()
        # Disable rate limits for tests.
        _default_limiter.requests_per_minute = 10_000
        _default_limiter.auth_requests_per_minute = 10_000

    def tearDown(self) -> None:
        self._vault_patcher.stop()
        self.engine.dispose()


class TestVaultSyncedBroadcast(VaultSyncBroadcastTestBase):
    """Creating/updating notes from Obsidian should broadcast vault_synced."""

    def test_create_obsidian_note_broadcasts_vault_synced(self) -> None:
        with self.Session() as db:
            client = _build_client(db)
            try:
                with (
                    patch("routers.websocket.broadcast_vault_synced") as mock_broadcast,
                    patch("routers.websocket.broadcast_note_created"),
                ):
                    response = client.post(
                        "/notes/",
                        json={
                            "title": "Vault Note",
                            "content": "From Obsidian",
                            "tags": ["vault"],
                            "source": "obsidian",
                            "source_path": "/vault/note.md",
                        },
                        headers={"X-From-Vault": "1"},
                    )
                    self.assertEqual(response.status_code, 201)
                    mock_broadcast.assert_called_once()
                    call_args = mock_broadcast.call_args
                    self.assertEqual(call_args.args[1], "Vault Note")
            finally:
                _teardown_client(client)

    def test_create_non_obsidian_note_does_not_broadcast_vault_synced(self) -> None:
        with self.Session() as db:
            client = _build_client(db)
            try:
                with (
                    patch("routers.websocket.broadcast_vault_synced") as mock_broadcast,
                    patch("routers.websocket.broadcast_note_created"),
                ):
                    response = client.post(
                        "/notes/",
                        json={
                            "title": "Manual Note",
                            "content": "Typed by hand",
                            "tags": [],
                            "source": "joidy",
                        },
                    )
                    self.assertEqual(response.status_code, 201)
                    mock_broadcast.assert_not_called()
            finally:
                _teardown_client(client)

    def test_update_obsidian_note_broadcasts_vault_synced(self) -> None:
        with self.Session() as db:
            client = _build_client(db)
            try:
                # Create an obsidian note first.
                create_res = client.post(
                    "/notes/",
                    json={
                        "title": "Original Vault",
                        "content": "v1",
                        "tags": [],
                        "source": "obsidian",
                        "source_path": "/vault/update.md",
                    },
                    headers={"X-From-Vault": "1"},
                )
                note_id = create_res.json()["id"]

                with (
                    patch("routers.websocket.broadcast_vault_synced") as mock_broadcast,
                    patch("routers.websocket.broadcast_note_updated"),
                ):
                    update_res = client.put(
                        f"/notes/{note_id}",
                        json={
                            "title": "Updated Vault",
                            "content": "v2 with more text to trigger edit event",
                            "source": "obsidian",
                            "source_path": "/vault/update.md",
                        },
                        headers={"X-From-Vault": "1"},
                    )
                    self.assertEqual(update_res.status_code, 200)
                    mock_broadcast.assert_called_once()
                    self.assertEqual(mock_broadcast.call_args.args[1], "Updated Vault")
            finally:
                _teardown_client(client)


class TestSyncStatusEndpoint(VaultSyncBroadcastTestBase):
    """GET /sync/status returns last_sync_time, pending_conflicts, total_synced."""

    def test_status_empty_database(self) -> None:
        with self.Session() as db:
            client = _build_client(db)
            try:
                response = client.get("/sync/status")
                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertIsNone(data["last_sync_time"])
                self.assertEqual(data["pending_conflicts"], 0)
                self.assertEqual(data["total_synced"], 0)
                self.assertIsNotNone(data["server_time"])
            finally:
                _teardown_client(client)

    def test_status_counts_obsidian_notes(self) -> None:
        with self.Session() as db:
            db.add(Note(title="A", content="c", source="obsidian", source_path="/v/a.md"))
            db.add(Note(title="B", content="c", source="obsidian", source_path="/v/b.md"))
            db.add(Note(title="C", content="c", source="joidy"))
            db.commit()

            client = _build_client(db)
            try:
                response = client.get("/sync/status")
                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertEqual(data["total_synced"], 2)
            finally:
                _teardown_client(client)

    def test_status_reports_pending_conflicts(self) -> None:
        with self.Session() as db:
            note = Note(title="Conflicted", content="c", source="obsidian", source_path="/v/c.md")
            db.add(note)
            db.flush()
            db.add(
                SyncState(
                    note_id=note.id,
                    conflict=True,
                    local_mtime=datetime(2024, 1, 1, tzinfo=timezone.utc),
                    remote_mtime=datetime(2024, 1, 2, tzinfo=timezone.utc),
                )
            )
            db.commit()

            client = _build_client(db)
            try:
                response = client.get("/sync/status")
                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertEqual(data["pending_conflicts"], 1)
            finally:
                _teardown_client(client)

    def test_status_reports_last_sync_time(self) -> None:
        with self.Session() as db:
            note = Note(title="Synced", content="c", source="obsidian", source_path="/v/s.md")
            db.add(note)
            db.flush()
            sync_time = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
            db.add(SyncState(note_id=note.id, conflict=False, last_synced_at=sync_time))
            db.commit()

            client = _build_client(db)
            try:
                response = client.get("/sync/status")
                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertIsNotNone(data["last_sync_time"])
                self.assertIn("2024-06-15", data["last_sync_time"])
            finally:
                _teardown_client(client)


class TestWebSocketBroadcastFunctions(unittest.TestCase):
    """The broadcast_* helper functions schedule tasks on the running loop."""

    def test_broadcast_vault_synced_no_running_loop_is_noop(self) -> None:
        # Outside an event loop, broadcast_vault_synced should not raise.
        from routers.websocket import broadcast_vault_synced

        broadcast_vault_synced(1, "Test", "/vault/test.md")  # should not raise

    def test_broadcast_vault_sync_started_no_running_loop_is_noop(self) -> None:
        from routers.websocket import broadcast_vault_sync_started

        broadcast_vault_sync_started()  # should not raise

    def test_broadcast_vault_sync_complete_no_running_loop_is_noop(self) -> None:
        from routers.websocket import broadcast_vault_sync_complete

        broadcast_vault_sync_complete(5)  # should not raise


if __name__ == "__main__":
    unittest.main()
