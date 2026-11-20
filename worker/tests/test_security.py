"""Regression tests for the worker security-hardening bundle.

Covers the worker-service findings from audit #1273:
- #1298 (W-03): vault files are read behind a ``stat().st_size`` cap so a
  multi-GB ``.md`` cannot OOM the worker or flood the API.
- #1294 (W-02): rows replayed from the persistent event log are re-validated
  like live ``awatch`` events — the log is host-writable with no integrity
  check, so injected paths must never reach the processing queue.
- #1299 (W-04): ``/health`` reports a fixed exception identifier only — never
  ``repr(exc)``/``str(exc)`` with embedded URLs, paths, or exception detail.
- #1301 (W-06): vault filenames are escaped before logging so a name with
  newlines/ANSI codes cannot forge log lines in ``docker logs``.
- #1300 (W-05): the worker's ``/vault`` bind mount is read-only.
"""

import json
import os
import re
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import HTTPServer
from pathlib import Path
from unittest.mock import AsyncMock, patch

# Make worker sources importable from repo root during CI.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import task_status  # noqa: E402
from metrics_server import _MetricsHandler  # noqa: E402
from watchers import vault_watcher  # noqa: E402
from watchers.vault_watcher import (  # noqa: E402
    PersistentEventLog,
    _is_valid_vault_path,
    _log_name,
    _read_vault_file,
    _replay_pending_events,
    import_or_update_note,
)
from watchfiles import Change  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]


class FakeResponse:
    """Minimal httpx.Response stub for the mocked AsyncClient."""

    def __init__(self, status_code, json_data=None):
        self.status_code = status_code
        self._json = json_data or {}

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


def _make_client():
    client = AsyncMock()
    client.get.return_value = FakeResponse(200, [])
    client.post.return_value = FakeResponse(201)
    client.put.return_value = FakeResponse(200)
    client.delete.return_value = FakeResponse(204)
    return client


class TestFileSizeCap(unittest.TestCase):
    """#1298: stat() gate before read_text — oversized files are skipped."""

    def setUp(self):
        vault_watcher._oversized_warned.clear()

    def test_read_vault_file_returns_content_under_cap(self):
        with tempfile.TemporaryDirectory() as tmp:
            md = Path(tmp) / "note.md"
            md.write_text("hello", encoding="utf-8")
            assert _read_vault_file(md) == "hello"

    def test_read_vault_file_refuses_oversized(self):
        with tempfile.TemporaryDirectory() as tmp:
            md = Path(tmp) / "big.md"
            md.write_bytes(b"x" * 4096)
            with patch.object(vault_watcher.settings, "max_note_file_size", 16):
                assert _read_vault_file(md) is None

    def test_read_vault_file_missing_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            assert _read_vault_file(Path(tmp) / "missing.md") is None

    def test_oversized_warning_logged_once_per_path(self):
        """The issue asks for a single warning log per skipped file."""
        with tempfile.TemporaryDirectory() as tmp:
            md = Path(tmp) / "big.md"
            md.write_bytes(b"x" * 4096)
            with patch.object(vault_watcher.settings, "max_note_file_size", 16):
                with self.assertLogs("watchers.vault_watcher", level="WARNING") as cm:
                    _read_vault_file(md)
                    _read_vault_file(md)
                    _read_vault_file(md)
            hits = [r.getMessage() for r in cm.records if "oversized" in r.getMessage().lower()]
            self.assertEqual(len(hits), 1)


class TestFileSizeCapSync(unittest.IsolatedAsyncioTestCase):
    """#1298: an oversized note produces no API payload at all."""

    def setUp(self):
        vault_watcher._oversized_warned.clear()

    async def test_oversized_file_never_reaches_api(self):
        with tempfile.TemporaryDirectory() as tmp:
            md = Path(tmp) / "huge.md"
            md.write_bytes(b"x" * 8192)
            client = _make_client()
            with patch.object(vault_watcher.settings, "max_note_file_size", 16):
                await import_or_update_note(md, client, "token")
            assert client.get.call_count == 0
            assert client.post.call_count == 0
            assert client.put.call_count == 0


class TestReplayPathValidation(unittest.TestCase):
    """#1294: replayed/persisted paths get the same checks as live events."""

    def _vault(self, tmp: str) -> Path:
        root = Path(tmp) / "vault"
        root.mkdir()
        return root

    def test_valid_md_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._vault(tmp)
            md = root / "note.md"
            md.write_text("x", encoding="utf-8")
            assert _is_valid_vault_path(str(md), Change.added, root)
            assert _is_valid_vault_path(str(md), Change.modified, root)

    def test_issue_poc_env_path_rejected(self):
        """The issue's exact payload: ('/app/.env','added') must be refused."""
        with tempfile.TemporaryDirectory() as tmp:
            root = self._vault(tmp)
            assert not _is_valid_vault_path("/app/.env", Change.added, root)
            assert not _is_valid_vault_path("/app/.env", Change.modified, root)
            assert not _is_valid_vault_path("/app/.env", Change.deleted, root)

    def test_external_md_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._vault(tmp)
            outside = Path(tmp) / "outside.md"
            outside.write_text("secret", encoding="utf-8")
            assert not _is_valid_vault_path(str(outside), Change.added, root)

    def test_dotdot_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._vault(tmp)
            outside = Path(tmp) / "sneaky.md"
            outside.write_text("secret", encoding="utf-8")
            assert not _is_valid_vault_path(str(root / ".." / "sneaky.md"), Change.added, root)

    def test_joidy_dir_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._vault(tmp)
            jdir = root / "_joidy"
            jdir.mkdir()
            internal = jdir / "daily.md"
            internal.write_text("x", encoding="utf-8")
            assert not _is_valid_vault_path(str(internal), Change.added, root)

    def test_non_md_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._vault(tmp)
            txt = root / "note.txt"
            txt.write_text("x", encoding="utf-8")
            assert not _is_valid_vault_path(str(txt), Change.added, root)

    def test_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._vault(tmp)
            target = Path(tmp) / "target.md"
            target.write_text("x", encoding="utf-8")
            link = root / "link.md"
            try:
                link.symlink_to(target)
            except OSError:
                self.skipTest("symlinks not supported on this platform")
            assert not _is_valid_vault_path(str(link), Change.added, root)

    def test_directory_named_md_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._vault(tmp)
            (root / "weird.md").mkdir()
            assert not _is_valid_vault_path(str(root / "weird.md"), Change.added, root)

    def test_deleted_event_allows_missing_file(self):
        """A delete event arrives after the file is gone — containment and
        suffix checks still apply, but non-existence is expected."""
        with tempfile.TemporaryDirectory() as tmp:
            root = self._vault(tmp)
            assert _is_valid_vault_path(str(root / "gone.md"), Change.deleted, root)
            # ...but an injected delete for an outside path is still refused.
            assert not _is_valid_vault_path(str(Path(tmp) / "gone.md"), Change.deleted, root)


class TestReplayPendingEvents(unittest.TestCase):
    """#1294: poisoned event-log rows are refused and dropped on replay."""

    def test_injected_row_dropped_legit_row_replayed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            legit = root / "pending.md"
            legit.write_text("x", encoding="utf-8")
            db = Path(tmp) / "events.db"

            # Poison the log while the worker is "down" (crash recovery path).
            log = PersistentEventLog(db)
            log.add("/app/.env", Change.added)
            log.add(str(legit), Change.added)
            log.close()

            log2 = PersistentEventLog(db)
            with self.assertLogs("watchers.vault_watcher", level="WARNING") as cm:
                accepted = _replay_pending_events(log2, root)
            log2.close()

            self.assertEqual(accepted, {str(legit): Change.added})

            # The poisoned row was deleted from the log — not just skipped —
            # so it cannot be retried on the next startup either.
            log3 = PersistentEventLog(db)
            self.assertEqual(log3.pending(), [(str(legit), Change.added)])
            log3.close()

            self.assertTrue(any(".env" in r.getMessage() for r in cm.records))

    def test_empty_log_replays_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            log = PersistentEventLog(Path(tmp) / "events.db")
            self.assertEqual(_replay_pending_events(log, root), {})
            log.close()


class TestHealthErrorReporting(unittest.TestCase):
    """#1299: /health reports a fixed reason — never repr(exc) with URLs/paths."""

    def setUp(self):
        with task_status._lock:
            task_status._tasks.clear()

    def tearDown(self):
        with task_status._lock:
            task_status._tasks.clear()

    def test_mark_crashed_stores_type_name_only(self):
        task_status.mark_crashed(
            "vault_watcher",
            RuntimeError("GET http://api:8000/notes/?source_path=/vault/secret.md failed"),
        )
        error = task_status.snapshot()["vault_watcher"]["error"]
        self.assertEqual(error, "RuntimeError")
        for leaked in ("http", "secret.md", "/vault", "source_path"):
            self.assertNotIn(leaked, error)

    def test_health_endpoint_leaks_no_exception_details(self):
        """curl /health after a crash → no exception text, URLs, or paths."""
        task_status.record_start("vault_watcher")
        task_status.mark_crashed(
            "vault_watcher",
            RuntimeError("GET http://api:8000/notes/?source_path=/vault/secret.md failed"),
        )

        server = HTTPServer(("127.0.0.1", 0), _MetricsHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5)
            self.assertEqual(ctx.exception.code, 503)
            body = ctx.exception.read().decode()

            data = json.loads(body)
            self.assertEqual(data["status"], "degraded")
            self.assertEqual(data["tasks"]["vault_watcher"]["error"], "RuntimeError")
            for leaked in ("http://", "secret.md", "/vault", "source_path", "GET "):
                self.assertNotIn(leaked, body)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


class TestFilenameSanitization(unittest.TestCase):
    """#1301: filenames are escaped before reaching any log line."""

    def test_log_name_escapes_newline_and_ansi(self):
        safe = _log_name("/vault/evil\nINFO forged\x1b[31m.md")
        self.assertNotIn("\n", safe)
        self.assertNotIn("\x1b", safe)
        self.assertIn("\\n", safe)  # newline survives as a visible escape

    def test_log_name_shows_basename_only(self):
        safe = _log_name("/vault/deep/nested/note.md")
        self.assertNotIn("deep", safe)
        self.assertNotIn("nested", safe)


class TestLoggedFilenamesAreEscaped(unittest.IsolatedAsyncioTestCase):
    """#1301: end-to-end — an evil filename cannot forge extra log lines."""

    def setUp(self):
        vault_watcher._oversized_warned.clear()

    async def test_synced_log_line_escapes_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            md = Path(tmp) / "evil\nINFO forged.md"
            md.write_text("x", encoding="utf-8")
            client = _make_client()
            with patch("watchers.vault_watcher.get_auth_token", new=AsyncMock(return_value="token")):
                with self.assertLogs("watchers.vault_watcher", level="INFO") as cm:
                    await import_or_update_note(md, client, "token")
            synced = [r.getMessage() for r in cm.records if "Synced" in r.getMessage()]
            self.assertEqual(len(synced), 1)
            # Single line: the raw newline in the filename was escaped.
            self.assertNotIn("\n", synced[0])
            self.assertIn("forged", synced[0])  # name still identifiable


class TestComposeVaultMountReadOnly(unittest.TestCase):
    """#1300: the worker must not get a writable /vault mount."""

    def _worker_block(self, compose: Path) -> str:
        text = compose.read_text(encoding="utf-8")
        match = re.search(r"^  worker:\n(.*?)(?=^  \S|\Z)", text, re.S | re.M)
        self.assertIsNotNone(match, f"no worker service in {compose.name}")
        return match.group(1)

    @unittest.skipUnless(
        (REPO_ROOT / "docker-compose.yml").exists(),
        "compose files not present (tests running inside the worker image)",
    )
    def test_worker_vault_mount_is_read_only(self):
        for name in ("docker-compose.yml", "docker-compose.dev.yml"):
            block = self._worker_block(REPO_ROOT / name)
            mounts = [ln.strip() for ln in block.splitlines() if ":/vault" in ln]
            self.assertTrue(mounts, f"no /vault mount found in {name} worker service")
            for mount in mounts:
                self.assertTrue(
                    mount.endswith(":ro"),
                    f"{name}: worker /vault mount is not read-only: {mount}",
                )


if __name__ == "__main__":
    unittest.main()
