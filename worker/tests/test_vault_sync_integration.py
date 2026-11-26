"""Integration tests for Obsidian vault watcher sync (#12).

Simulates filesystem writes (create/modify/delete) against a temporary vault
directory and verifies the watcher's event consumer calls the API correctly.
Also covers rename detection (delete+add with identical content), concurrent
edits, and the 2s debounce behaviour.
"""

import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

# Make worker sources importable from repo root during CI.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import auth
from watchers import vault_watcher
from watchers.vault_watcher import (
    PersistentEventLog,
    VaultEvent,
    _consume_vault_events,
    _Fingerprint,
    _fingerprint,
)
from watchfiles import Change


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


def _make_client(responses):
    """Build an AsyncMock httpx client that pops responses in order.

    ``responses`` is a list of (method, FakeResponse) tuples. Any call whose
    method has no queued response falls back to a 200/[] default.
    """
    client = AsyncMock()
    queue = list(responses)

    async def _get(*args, **kwargs):
        return _next("GET")

    async def _post(*args, **kwargs):
        return _next("POST")

    async def _put(*args, **kwargs):
        return _next("PUT")

    async def _delete(*args, **kwargs):
        return _next("DELETE")

    def _next(method):
        for i, (m, _resp) in enumerate(queue):
            if m == method:
                return queue.pop(i)[1]
        # Default: empty list for GET, generic 200 otherwise.
        return FakeResponse(200, [] if method == "GET" else {})

    client.get.side_effect = _get
    client.post.side_effect = _post
    client.put.side_effect = _put
    client.delete.side_effect = _delete
    return client


def _write_md(path: Path, title: str, body: str, tags=None) -> str:
    """Write a markdown file with frontmatter and return its content."""
    tags = tags or []
    fm = f"---\ntitle: {title}\ntags: [{', '.join(tags)}]\n---\n\n{body}\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(fm, encoding="utf-8")
    return fm


async def _run_consumer_once(queue, client, *, vault=None, debounce=0.05, flush=0.02):
    """Run the consumer loop for a single batch then stop it.

    Patches the debounce/flush intervals to keep tests fast, and sets the
    shutdown event after the first batch completes so the loop exits cleanly.
    ``vault`` is the directory treated as the vault root for the containment
    check (#1293); it defaults to the system temp dir since test vaults are
    TemporaryDirectory instances.
    """
    event_log = PersistentEventLog(os.path.join(tempfile.gettempdir(), "test_events.db"))
    try:
        with (
            patch("watchers.vault_watcher.DEBOUNCE_SECONDS", debounce),
            patch("watchers.vault_watcher.QUEUE_FLUSH_INTERVAL", flush),
            patch("watchers.vault_watcher.get_auth_token", new=AsyncMock(return_value="token")),
            patch.object(vault_watcher.settings, "vault_path", str(vault or tempfile.gettempdir())),
        ):
            consumer_task = asyncio.create_task(_consume_vault_events(queue, client, "token", event_log))
            # Wait until the consumer has processed the batch (queue drained
            # + debounce elapsed) then trigger shutdown.
            await asyncio.sleep(debounce + flush + 0.3)
            vault_watcher.shutdown_event.set()
            await asyncio.wait_for(consumer_task, timeout=5.0)
    finally:
        event_log.close()
        vault_watcher.shutdown_event.clear()


class TestVaultFilesystemMock(unittest.TestCase):
    """Requirement: Mock del filesystem de Obsidian (directorio /vault temporal)."""

    def test_temp_vault_create_and_read(self):
        with tempfile.TemporaryDirectory() as vault:
            vault_path = Path(vault)
            md = vault_path / "note.md"
            content = _write_md(md, "Test", "Hello #tag")
            assert md.exists()
            assert md.read_text(encoding="utf-8") == content

    def test_temp_vault_subdirectories(self):
        with tempfile.TemporaryDirectory() as vault:
            vault_path = Path(vault)
            md = vault_path / "folder" / "sub" / "deep.md"
            _write_md(md, "Deep", "Nested note")
            assert md.exists()

    def test_temp_vault_joidy_dir_excluded(self):
        with tempfile.TemporaryDirectory() as vault:
            vault_path = Path(vault)
            joidy_md = vault_path / "_joidy" / "daily.md"
            _write_md(joidy_md, "Daily", "Internal")
            assert vault_watcher._is_joidy_file(str(joidy_md))


class TestVaultWatcherIntegration(unittest.IsolatedAsyncioTestCase):
    """Integration: filesystem events → API calls."""

    async def test_create_md_file_triggers_note_creation(self):
        """Requirement: crear archivo .md → watcher detecta → DB se actualiza."""
        with tempfile.TemporaryDirectory() as vault:
            vault_path = Path(vault)
            md = vault_path / "new_note.md"
            _write_md(md, "New Note", "Content #fresh", ["work"])

            queue = asyncio.Queue()
            await queue.put(VaultEvent(path=str(md), change_type=Change.added))

            client = _make_client(
                [
                    ("GET", FakeResponse(200, [])),  # no existing note
                    ("POST", FakeResponse(201)),  # create
                ]
            )

            await _run_consumer_once(queue, client, vault=vault)

            assert client.post.call_count == 1
            payload = client.post.call_args.kwargs["json"]
            assert payload["title"] == "New Note"
            assert payload["source_path"] == str(md)
            assert "fresh" in payload["tags"]

    async def test_modify_md_file_triggers_note_update(self):
        """Requirement: modificar archivo .md → DB refleja cambios."""
        with tempfile.TemporaryDirectory() as vault:
            vault_path = Path(vault)
            md = vault_path / "existing.md"
            _write_md(md, "Updated", "New content #edited", ["work"])

            queue = asyncio.Queue()
            await queue.put(VaultEvent(path=str(md), change_type=Change.modified))

            client = _make_client(
                [
                    ("GET", FakeResponse(200, [{"id": 42, "source_path": str(md)}])),
                    ("PUT", FakeResponse(200)),
                ]
            )

            await _run_consumer_once(queue, client, vault=vault)

            assert client.put.call_count == 1
            url = client.put.call_args.args[0]
            assert url.endswith("/notes/42")
            payload = client.put.call_args.kwargs["json"]
            assert payload["title"] == "Updated"
            assert "edited" in payload["tags"]

    async def test_delete_md_file_triggers_note_deletion(self):
        """Requirement: eliminar archivo .md → DB marca como eliminado."""
        with tempfile.TemporaryDirectory() as vault:
            vault_path = Path(vault)
            md = vault_path / "doomed.md"
            _write_md(md, "Doomed", "Bye")
            md.unlink()

            queue = asyncio.Queue()
            await queue.put(VaultEvent(path=str(md), change_type=Change.deleted))

            client = _make_client(
                [
                    (
                        "GET",
                        FakeResponse(
                            200,
                            [{"id": 99, "source_path": str(md), "updated_at": "2025-01-01T00:00:00Z"}],
                        ),
                    ),
                    ("DELETE", FakeResponse(200)),
                ]
            )

            await _run_consumer_once(queue, client, vault=vault)

            # Atomic delete: server-side source_path match + updated_at etag
            # (#1302), not list-then-delete by id.
            assert client.delete.call_count == 1
            url = client.delete.call_args.args[0]
            assert url.endswith("/notes/by-path")
            params = client.delete.call_args.kwargs["params"]
            assert params["source_path"] == str(md)
            assert params["expected_updated_at"] == "2025-01-01T00:00:00Z"

    async def test_concurrent_edits_two_files_both_sync(self):
        """Requirement: escritura concurrente desde API y vault (conflictos).

        Two different files edited concurrently should both sync independently
        without interfering with each other.
        """
        with tempfile.TemporaryDirectory() as vault:
            vault_path = Path(vault)
            md_a = vault_path / "alpha.md"
            md_b = vault_path / "beta.md"
            _write_md(md_a, "Alpha", "Content A")
            _write_md(md_b, "Beta", "Content B")

            queue = asyncio.Queue()
            await queue.put(VaultEvent(path=str(md_a), change_type=Change.added))
            await queue.put(VaultEvent(path=str(md_b), change_type=Change.added))

            client = _make_client(
                [
                    ("GET", FakeResponse(200, [])),
                    ("GET", FakeResponse(200, [])),
                    ("POST", FakeResponse(201)),
                    ("POST", FakeResponse(201)),
                ]
            )

            await _run_consumer_once(queue, client, vault=vault)

            assert client.post.call_count == 2
            paths = [call.kwargs["json"]["source_path"] for call in client.post.call_args_list]
            assert str(md_a) in paths
            assert str(md_b) in paths

    async def test_rename_detection_pairs_delete_and_add(self):
        """Concurrent conflict scenario: delete + add with identical content
        is treated as a rename (PUT source_path), not delete + create (#364)."""
        with tempfile.TemporaryDirectory() as vault:
            vault_path = Path(vault)
            old_path = vault_path / "old_name.md"
            new_path = vault_path / "new_name.md"
            content = _write_md(old_path, "Renamed", "Same content #move")

            # Seed the fingerprint for the old path so the consumer can match.
            vault_watcher._fingerprints[str(old_path)] = _Fingerprint(
                _fingerprint(content), len(content.encode("utf-8"))
            )

            # Simulate the rename: old file deleted, new file created with same content.
            old_path.unlink()
            new_path.write_text(content, encoding="utf-8")

            queue = asyncio.Queue()
            await queue.put(VaultEvent(path=str(old_path), change_type=Change.deleted))
            await queue.put(VaultEvent(path=str(new_path), change_type=Change.added))

            client = _make_client(
                [
                    ("GET", FakeResponse(200, [{"id": 55, "source_path": str(old_path)}])),
                    ("PUT", FakeResponse(200)),  # rename → update source_path
                ]
            )

            await _run_consumer_once(queue, client, vault=vault)

            # Rename path: PUT to update source_path, no DELETE, no POST.
            assert client.put.call_count == 1
            assert client.delete.call_count == 0
            assert client.post.call_count == 0
            url = client.put.call_args.args[0]
            assert url.endswith("/notes/55")
            payload = client.put.call_args.kwargs["json"]
            assert payload["source_path"] == str(new_path)

            # Cleanup fingerprints
            vault_watcher._fingerprints.pop(str(old_path), None)
            vault_watcher._fingerprints.pop(str(new_path), None)


class TestVaultDebounce(unittest.IsolatedAsyncioTestCase):
    """Requirement: debounce de 2s del watcher."""

    async def test_debounce_delays_processing(self):
        """The consumer waits DEBOUNCE_SECONDS before processing a batch."""
        with tempfile.TemporaryDirectory() as vault:
            vault_path = Path(vault)
            md = vault_path / "debounced.md"
            _write_md(md, "Debounce", "Content")

            queue = asyncio.Queue()
            await queue.put(VaultEvent(path=str(md), change_type=Change.added))

            client = _make_client(
                [
                    ("GET", FakeResponse(200, [])),
                    ("POST", FakeResponse(201)),
                ]
            )

            # Use a longer debounce to verify timing.
            elapsed = await self._timed_consumer(queue, client, debounce=0.3, flush=0.02, vault=vault)

            assert elapsed >= 0.3, f"Debounce not respected: {elapsed:.3f}s < 0.3s"
            assert client.post.call_count == 1

    async def test_debounce_dedups_rapid_events_for_same_file(self):
        """Multiple rapid events for the same file produce a single API call."""
        with tempfile.TemporaryDirectory() as vault:
            vault_path = Path(vault)
            md = vault_path / "rapid.md"
            _write_md(md, "Rapid", "v1")

            queue = asyncio.Queue()
            # Simulate Obsidian writing rapidly: added, modified, modified.
            await queue.put(VaultEvent(path=str(md), change_type=Change.added))
            await queue.put(VaultEvent(path=str(md), change_type=Change.modified))
            await queue.put(VaultEvent(path=str(md), change_type=Change.modified))

            client = _make_client(
                [
                    ("GET", FakeResponse(200, [])),
                    ("POST", FakeResponse(201)),
                ]
            )

            await _run_consumer_once(queue, client, vault=vault, debounce=0.05, flush=0.02)

            # Dedup: only one POST despite three events for the same path.
            assert client.post.call_count == 1

    async def _timed_consumer(self, queue, client, *, debounce, flush, vault=None):
        """Run the consumer and return elapsed wall-clock time."""
        import time

        event_log = PersistentEventLog(os.path.join(tempfile.gettempdir(), "test_events.db"))
        start = time.monotonic()
        try:
            with (
                patch("watchers.vault_watcher.DEBOUNCE_SECONDS", debounce),
                patch("watchers.vault_watcher.QUEUE_FLUSH_INTERVAL", flush),
                patch("watchers.vault_watcher.get_auth_token", new=AsyncMock(return_value="token")),
                patch.object(vault_watcher.settings, "vault_path", str(vault or tempfile.gettempdir())),
            ):
                consumer_task = asyncio.create_task(_consume_vault_events(queue, client, "token", event_log))
                await asyncio.sleep(debounce + flush + 0.3)
                vault_watcher.shutdown_event.set()
                await asyncio.wait_for(consumer_task, timeout=5.0)
        finally:
            event_log.close()
            vault_watcher.shutdown_event.clear()
        return time.monotonic() - start


class TestVaultConflictEdgeCases(unittest.IsolatedAsyncioTestCase):
    """Additional conflict / edge-case coverage."""

    async def test_delete_without_matching_note_is_noop(self):
        """Deleting a file that has no corresponding DB note should not error."""
        with tempfile.TemporaryDirectory() as vault:
            vault_path = Path(vault)
            md = vault_path / "orphan.md"
            _write_md(md, "Orphan", "No DB entry")
            md.unlink()

            queue = asyncio.Queue()
            await queue.put(VaultEvent(path=str(md), change_type=Change.deleted))

            client = _make_client(
                [
                    ("GET", FakeResponse(200, [])),  # no notes match
                ]
            )

            await _run_consumer_once(queue, client, vault=vault)

            assert client.delete.call_count == 0
            assert client.post.call_count == 0

    async def test_joidy_dir_events_not_processed(self):
        """Events for files inside _joidy/ are filtered by the watcher loop,
        not by the consumer. Verify the filter helper used by watch_vault."""
        assert vault_watcher._is_joidy_file("/vault/_joidy/daily.md")
        assert vault_watcher._is_joidy_file("/vault/notes/_joidy/x.md")
        assert not vault_watcher._is_joidy_file("/vault/notes/real.md")

    async def test_modify_then_delete_same_batch_deletes(self):
        """A modify followed by a delete in the same batch: last-write-wins
        on the dedup dict means the file is deleted, not updated."""
        with tempfile.TemporaryDirectory() as vault:
            vault_path = Path(vault)
            md = vault_path / "transient.md"
            _write_md(md, "Transient", "Soon gone")
            md.unlink()

            queue = asyncio.Queue()
            await queue.put(VaultEvent(path=str(md), change_type=Change.modified))
            await queue.put(VaultEvent(path=str(md), change_type=Change.deleted))

            client = _make_client(
                [
                    ("GET", FakeResponse(200, [{"id": 77, "source_path": str(md)}])),
                    ("DELETE", FakeResponse(204)),
                ]
            )

            await _run_consumer_once(queue, client, vault=vault)

            # Last event wins → delete.
            assert client.delete.call_count == 1
            assert client.put.call_count == 0


class TestVaultSymlinkSecurity(unittest.IsolatedAsyncioTestCase):
    """Vault reads must never follow symlinks or escape the vault root —
    ``ln -s /app/.env vault/leak.md`` would otherwise store secrets as a note
    readable via the API (#1293)."""

    async def test_symlink_event_never_reaches_api(self):
        with tempfile.TemporaryDirectory() as vault, tempfile.TemporaryDirectory() as outside:
            secret = Path(outside) / ".env"
            secret.write_text("SECRET_KEY=abc\nPOSTGRES_PASSWORD=x", encoding="utf-8")
            link = Path(vault) / "leak.md"
            link.symlink_to(secret)

            queue = asyncio.Queue()
            await queue.put(VaultEvent(path=str(link), change_type=Change.added))

            client = _make_client([])
            await _run_consumer_once(queue, client, vault=vault)

            assert client.get.call_count == 0
            assert client.post.call_count == 0
            assert client.put.call_count == 0
            assert client.delete.call_count == 0

    async def test_symlinked_parent_dir_escape_is_skipped(self):
        """A file under a symlinked dir inside the vault resolves outside the
        vault root and must be skipped, even though the path itself is not a
        symlink (#1293)."""
        with tempfile.TemporaryDirectory() as vault, tempfile.TemporaryDirectory() as outside:
            secret = Path(outside) / "escaped.md"
            secret.write_text("SECRET", encoding="utf-8")
            (Path(vault) / "linkdir").symlink_to(outside, target_is_directory=True)
            escaped = Path(vault) / "linkdir" / "escaped.md"

            queue = asyncio.Queue()
            await queue.put(VaultEvent(path=str(escaped), change_type=Change.added))

            client = _make_client([])
            await _run_consumer_once(queue, client, vault=vault)

            assert client.get.call_count == 0
            assert client.post.call_count == 0
            assert client.put.call_count == 0

    async def test_non_regular_file_event_is_skipped(self):
        """FIFOs/sockets/devices inside the vault are never read (#1293)."""
        with tempfile.TemporaryDirectory() as vault:
            fifo = Path(vault) / "pipe.md"
            os.mkfifo(fifo)

            queue = asyncio.Queue()
            await queue.put(VaultEvent(path=str(fifo), change_type=Change.added))

            client = _make_client([])
            await _run_consumer_once(queue, client, vault=vault)

            assert client.get.call_count == 0
            assert client.post.call_count == 0
            assert client.put.call_count == 0


class TestSyncRaces(unittest.IsolatedAsyncioTestCase):
    """#1302 (W-07): delete TOCTOU, fingerprint loss on restart, token
    stampede."""

    def tearDown(self):
        # Module-global fingerprint/auth state must not leak between tests.
        vault_watcher._unbind_event_log()
        vault_watcher._fingerprints.clear()
        auth._token_cache = None
        auth._refresh_generation = 0

    async def test_delete_and_add_across_restart_preserves_note(self):
        """AC: delete+create across a worker restart preserves the note
        id/history — the pair is reconciled as a rename, not a delete plus
        a fresh create that would also duplicate the note (#1302)."""
        with tempfile.TemporaryDirectory() as vault:
            root = Path(vault)
            old_path = root / "old_name.md"
            new_path = root / "new_name.md"
            db_path = root / "events.db"
            content = _write_md(old_path, "Renamed", "Same content #move")

            # Worker "v1" synced old_name.md (fingerprint persisted), then
            # recorded the delete+add events and crashed before processing.
            log = PersistentEventLog(db_path)
            log.set_fingerprint(str(old_path), _fingerprint(content), len(content.encode("utf-8")))
            log.add(str(old_path), Change.deleted)
            log.add(str(new_path), Change.added)
            log.close()
            old_path.unlink()
            new_path.write_text(content, encoding="utf-8")

            # Worker "v2" boots: binds the log (seeds _fingerprints), replays
            # pending events through the same batch pipeline, THEN scans —
            # so the scan sees the renamed note and cannot duplicate it.
            log2 = PersistentEventLog(db_path)
            vault_watcher._bind_event_log(log2)
            try:
                replayed = vault_watcher._replay_pending_events(log2, root)
                client = _make_client(
                    [
                        # rename_note_path lookup by OLD source_path.
                        ("GET", FakeResponse(200, [{"id": 55, "source_path": str(old_path)}])),
                        ("PUT", FakeResponse(200)),
                        # initial_scan's bulk source-paths check confirms the
                        # API holds the renamed note — with the fingerprint
                        # recorded during the rename the unchanged file is
                        # skipped outright, no lookup or create.
                        ("GET", FakeResponse(200, [str(new_path)])),
                        ("POST", FakeResponse(200)),  # rebuild-derived
                    ]
                )
                with (
                    patch("watchers.vault_watcher.get_auth_token", new=AsyncMock(return_value="token")),
                    patch.object(vault_watcher.settings, "vault_path", vault),
                ):
                    await vault_watcher._process_batch(replayed, client, "token", log2)
                    await vault_watcher.initial_scan(root, client, "token")

                # Same note id updated in place — no delete, no create.
                assert client.delete.call_count == 0
                note_creates = [c for c in client.post.call_args_list if "json" in c.kwargs]
                assert note_creates == []
                put_urls = [c.args[0] for c in client.put.call_args_list]
                assert put_urls and all(u.endswith("/notes/55") for u in put_urls)
                rename_payload = client.put.call_args_list[0].kwargs["json"]
                assert rename_payload["source_path"] == str(new_path)

                # Events consumed → removed from the persistent log.
                assert log2.pending() == []
            finally:
                log2.close()

    async def test_delete_event_for_recreated_file_resyncs_not_deletes(self):
        """Delete TOCTOU: the file reappeared before the delete event was
        processed (recreated in the debounce window or while down) — the
        note is resynced in place, never deleted (#1302)."""
        with tempfile.TemporaryDirectory() as vault:
            md = Path(vault) / "back.md"
            _write_md(md, "Back", "Recreated content")

            queue = asyncio.Queue()
            await queue.put(VaultEvent(path=str(md), change_type=Change.deleted))

            client = _make_client(
                [
                    ("GET", FakeResponse(200, [{"id": 7, "source_path": str(md)}])),
                    ("PUT", FakeResponse(200)),
                ]
            )

            await _run_consumer_once(queue, client, vault=vault)

            assert client.delete.call_count == 0
            assert client.put.call_count == 1
            assert client.put.call_args.args[0].endswith("/notes/7")

    async def test_delete_note_by_path_uses_atomic_endpoint_with_etag(self):
        """The delete carries source_path + the updated_at etag captured at
        lookup, so the API can refuse a note that changed in between."""
        md = "/vault/doomed.md"
        client = _make_client(
            [
                (
                    "GET",
                    FakeResponse(200, [{"id": 9, "source_path": md, "updated_at": "2025-06-01T10:00:00Z"}]),
                ),
                ("DELETE", FakeResponse(200)),
            ]
        )

        await vault_watcher.delete_note_by_path(md, client, "token")

        assert client.delete.call_count == 1
        assert client.delete.call_args.args[0].endswith("/notes/by-path")
        params = client.delete.call_args.kwargs["params"]
        assert params == {"source_path": md, "expected_updated_at": "2025-06-01T10:00:00Z"}

    async def test_delete_note_by_path_respects_409_conflict(self):
        """409 = note changed since the lookup — leave it untouched instead
        of deleting a note that was recreated or updated in between."""
        md = "/vault/conflicted.md"
        client = _make_client(
            [
                ("GET", FakeResponse(200, [{"id": 9, "source_path": md, "updated_at": "t0"}])),
                ("DELETE", FakeResponse(409)),
            ]
        )

        await vault_watcher.delete_note_by_path(md, client, "token")

        assert client.delete.call_count == 1  # refused once, not retried

    async def test_fingerprint_persisted_via_bound_event_log(self):
        """_record_fingerprint writes through to the bound event log, so a
        fresh worker process can still pair a delete+add rename (#1302)."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "events.db"
            log = PersistentEventLog(db_path)
            vault_watcher._bind_event_log(log)
            try:
                vault_watcher._record_fingerprint("/vault/x.md", "f00d")
            finally:
                log.close()

            # "Restart": a new log instance sees the persisted fingerprint —
            # size is NULL for a path that does not exist, which is fine:
            # matching still works on hash alone (#1537).
            log2 = PersistentEventLog(db_path)
            assert log2.fingerprints() == {"/vault/x.md": _Fingerprint("f00d")}
            vault_watcher._bind_event_log(log2)
            try:
                assert vault_watcher._fingerprints["/vault/x.md"].hash == "f00d"
                vault_watcher._drop_fingerprint("/vault/x.md")
                assert log2.fingerprints() == {}
            finally:
                log2.close()

    async def test_failed_sync_keeps_event_pending_for_next_startup(self):
        """#1534: exhausted retries must not remove the pending event —
        the note is retried on the next startup instead of silently lost."""
        with tempfile.TemporaryDirectory() as vault:
            md = Path(vault) / "flaky.md"
            _write_md(md, "Flaky", "body that never syncs")

            log = PersistentEventLog(Path(vault) / "events.db")
            try:
                log.add(str(md), Change.added)
                # Every lookup GET answers 503 -> import_or_update_note
                # exhausts its retries and reports failure.
                client = _make_client([("GET", FakeResponse(503))] * 3)
                with (
                    patch("watchers.vault_watcher.get_auth_token", new=AsyncMock(return_value="token")),
                    patch.object(vault_watcher.settings, "vault_path", vault),
                    patch("asyncio.sleep", new=AsyncMock()),
                ):
                    await vault_watcher._process_batch({str(md): Change.added}, client, "token", log)

                assert [p for p, _ in log.pending()] == [str(md)]
                assert str(md) not in vault_watcher._fingerprints
            finally:
                log.close()

    async def test_failed_delete_keeps_event_pending_for_next_startup(self):
        """#1534: a delete whose attempts all fail keeps the event — the
        note is not reported deleted while it still exists."""
        with tempfile.TemporaryDirectory() as vault:
            md = Path(vault) / "doomed.md"  # already gone — pure delete event
            note = {"id": 9, "source_path": str(md), "updated_at": "t0"}

            log = PersistentEventLog(Path(vault) / "events.db")
            try:
                log.add(str(md), Change.deleted)
                responses = []
                for _ in range(3):
                    responses += [("GET", FakeResponse(200, [note])), ("DELETE", FakeResponse(503))]
                client = _make_client(responses)
                with (
                    patch("watchers.vault_watcher.get_auth_token", new=AsyncMock(return_value="token")),
                    patch.object(vault_watcher.settings, "vault_path", vault),
                    patch("asyncio.sleep", new=AsyncMock()),
                ):
                    await vault_watcher._process_batch({str(md): Change.deleted}, client, "token", log)

                assert [p for p, _ in log.pending()] == [str(md)]
            finally:
                log.close()

    async def test_failed_rename_keeps_both_events_pending(self):
        """#1534: exhausted rename retries keep BOTH events so the pair is
        reconciled as a rename again on the next startup."""
        with tempfile.TemporaryDirectory() as vault:
            root = Path(vault)
            old_path = root / "old.md"
            new_path = root / "new.md"
            content = _write_md(new_path, "Renamed", "same body #move")

            # Seed the rename fingerprint so the batch pairs delete+add.
            vault_watcher._fingerprints[str(old_path)] = _Fingerprint(
                _fingerprint(content), len(content.encode("utf-8"))
            )

            log = PersistentEventLog(root / "events.db")
            try:
                log.add(str(old_path), Change.deleted)
                log.add(str(new_path), Change.added)
                client = _make_client(
                    [
                        # rename lookup by OLD source_path finds the note…
                        ("GET", FakeResponse(200, [{"id": 55, "source_path": str(old_path)}])),
                        # …but every PUT attempt fails retryably.
                        *[("PUT", FakeResponse(503))] * 5,
                    ]
                )
                with (
                    patch("watchers.vault_watcher.get_auth_token", new=AsyncMock(return_value="token")),
                    patch.object(vault_watcher.settings, "vault_path", vault),
                    patch("asyncio.sleep", new=AsyncMock()),
                ):
                    await vault_watcher._process_batch(
                        {str(old_path): Change.deleted, str(new_path): Change.added},
                        client,
                        "token",
                        log,
                    )

                pending_paths = {p for p, _ in log.pending()}
                assert pending_paths == {str(old_path), str(new_path)}
            finally:
                log.close()


class TestTokenSingleFlight(unittest.IsolatedAsyncioTestCase):
    """AC: concurrent 401s trigger exactly one token fetch (#1302)."""

    def setUp(self):
        auth._token_cache = None
        auth._refresh_generation = 0

    def tearDown(self):
        auth._token_cache = None
        auth._refresh_generation = 0

    async def test_concurrent_force_refresh_fetches_once(self):
        calls = 0

        async def fake_fetch(client):
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.05)
            return "tok"

        client = AsyncMock()
        with patch("auth._fetch_token", new=fake_fetch):
            results = await asyncio.gather(*(auth.get_auth_token(client, force=True) for _ in range(10)))

        assert calls == 1
        assert results == ["tok"] * 10

    async def test_cached_token_reused_without_force(self):
        calls = 0

        async def fake_fetch(client):
            nonlocal calls
            calls += 1
            return "tok"

        client = AsyncMock()
        with patch("auth._fetch_token", new=fake_fetch):
            assert await auth.get_auth_token(client) == "tok"
            assert await auth.get_auth_token(client) == "tok"

        assert calls == 1

    async def test_new_401_after_completed_refresh_fetches_again(self):
        """A 401 arriving after a refresh finished must still force a fresh
        fetch — the single-flight only coalesces *concurrent* callers."""
        calls = 0

        async def fake_fetch(client):
            nonlocal calls
            calls += 1
            return f"tok{calls}"

        client = AsyncMock()
        with patch("auth._fetch_token", new=fake_fetch):
            assert await auth.get_auth_token(client, force=True) == "tok1"
            assert await auth.get_auth_token(client, force=True) == "tok2"

        assert calls == 2


if __name__ == "__main__":
    unittest.main()
