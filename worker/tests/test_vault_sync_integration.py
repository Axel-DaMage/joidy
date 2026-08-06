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

from watchers import vault_watcher
from watchers.vault_watcher import (
    PersistentEventLog,
    VaultEvent,
    _consume_vault_events,
    _fingerprint,
    import_or_update_note,
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
        for i, (m, resp) in enumerate(queue):
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


async def _run_consumer_once(queue, client, *, debounce=0.05, flush=0.02):
    """Run the consumer loop for a single batch then stop it.

    Patches the debounce/flush intervals to keep tests fast, and sets the
    shutdown event after the first batch completes so the loop exits cleanly.
    """
    event_log = PersistentEventLog(os.path.join(tempfile.gettempdir(), "test_events.db"))
    try:
        with patch("watchers.vault_watcher.DEBOUNCE_SECONDS", debounce), patch(
            "watchers.vault_watcher.QUEUE_FLUSH_INTERVAL", flush
        ), patch("watchers.vault_watcher.get_auth_token", new=AsyncMock(return_value="token")):
            consumer_task = asyncio.create_task(
                _consume_vault_events(queue, client, "token", event_log)
            )
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

            client = _make_client([
                ("GET", FakeResponse(200, [])),       # no existing note
                ("POST", FakeResponse(201)),           # create
            ])

            await _run_consumer_once(queue, client)

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

            client = _make_client([
                ("GET", FakeResponse(200, [{"id": 42, "source_path": str(md)}])),
                ("PUT", FakeResponse(200)),
            ])

            await _run_consumer_once(queue, client)

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

            queue = asyncio.Queue()
            await queue.put(VaultEvent(path=str(md), change_type=Change.deleted))

            client = _make_client([
                ("GET", FakeResponse(200, [{"id": 99, "source_path": str(md)}])),
                ("DELETE", FakeResponse(204)),
            ])

            await _run_consumer_once(queue, client)

            assert client.delete.call_count == 1
            url = client.delete.call_args.args[0]
            assert url.endswith("/notes/99")

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

            client = _make_client([
                ("GET", FakeResponse(200, [])),
                ("GET", FakeResponse(200, [])),
                ("POST", FakeResponse(201)),
                ("POST", FakeResponse(201)),
            ])

            await _run_consumer_once(queue, client)

            assert client.post.call_count == 2
            paths = [
                call.kwargs["json"]["source_path"]
                for call in client.post.call_args_list
            ]
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
            vault_watcher._fingerprints[str(old_path)] = _fingerprint(content)

            # Simulate the rename: old file deleted, new file created with same content.
            old_path.unlink()
            new_path.write_text(content, encoding="utf-8")

            queue = asyncio.Queue()
            await queue.put(VaultEvent(path=str(old_path), change_type=Change.deleted))
            await queue.put(VaultEvent(path=str(new_path), change_type=Change.added))

            client = _make_client([
                ("GET", FakeResponse(200, [{"id": 55, "source_path": str(old_path)}])),
                ("PUT", FakeResponse(200)),  # rename → update source_path
            ])

            await _run_consumer_once(queue, client)

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

            client = _make_client([
                ("GET", FakeResponse(200, [])),
                ("POST", FakeResponse(201)),
            ])

            # Use a longer debounce to verify timing.
            elapsed = await self._timed_consumer(queue, client, debounce=0.3, flush=0.02)

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

            client = _make_client([
                ("GET", FakeResponse(200, [])),
                ("POST", FakeResponse(201)),
            ])

            await _run_consumer_once(queue, client, debounce=0.05, flush=0.02)

            # Dedup: only one POST despite three events for the same path.
            assert client.post.call_count == 1

    async def _timed_consumer(self, queue, client, *, debounce, flush):
        """Run the consumer and return elapsed wall-clock time."""
        import time

        event_log = PersistentEventLog(os.path.join(tempfile.gettempdir(), "test_events.db"))
        start = time.monotonic()
        try:
            with patch("watchers.vault_watcher.DEBOUNCE_SECONDS", debounce), patch(
                "watchers.vault_watcher.QUEUE_FLUSH_INTERVAL", flush
            ), patch("watchers.vault_watcher.get_auth_token", new=AsyncMock(return_value="token")):
                consumer_task = asyncio.create_task(
                    _consume_vault_events(queue, client, "token", event_log)
                )
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

            queue = asyncio.Queue()
            await queue.put(VaultEvent(path=str(md), change_type=Change.deleted))

            client = _make_client([
                ("GET", FakeResponse(200, [])),  # no notes match
            ])

            await _run_consumer_once(queue, client)

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

            queue = asyncio.Queue()
            await queue.put(VaultEvent(path=str(md), change_type=Change.modified))
            await queue.put(VaultEvent(path=str(md), change_type=Change.deleted))

            client = _make_client([
                ("GET", FakeResponse(200, [{"id": 77, "source_path": str(md)}])),
                ("DELETE", FakeResponse(204)),
            ])

            await _run_consumer_once(queue, client)

            # Last event wins → delete.
            assert client.delete.call_count == 1
            assert client.put.call_count == 0


if __name__ == "__main__":
    unittest.main()
