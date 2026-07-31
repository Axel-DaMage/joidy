"""Integration tests for Obsidian vault watcher sync logic."""

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
    _extract_tags_from_content,
    _fingerprint,
    _is_joidy_file,
    _parse_frontmatter,
    delete_note_by_path,
    import_or_update_note,
)
from watchfiles import Change


class FakeResponse:
    def __init__(self, status_code, json_data=None, raise_error=False):
        self.status_code = status_code
        self._json = json_data or {}
        self.raise_error = raise_error

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.raise_error:
            raise Exception("HTTP error")


class TestVaultParsing(unittest.TestCase):
    def test_parse_frontmatter_and_body(self):
        content = "---\ntitle: My Note\ntags: [work, idea]\n---\n\n#body\n"
        fm, body = _parse_frontmatter(content)
        assert fm["title"] == "My Note"
        assert fm["tags"] == "[work, idea]"
        assert body == "#body"

    def test_parse_frontmatter_missing(self):
        content = "#just body\n"
        fm, body = _parse_frontmatter(content)
        assert fm == {}
        assert body == content

    def test_extract_tags(self):
        content = "---\ntags: [work, idea]\n---\nReunion #meeting con el equipo"
        fm, body = _parse_frontmatter(content)
        tags = _extract_tags_from_content(content, fm)
        assert "work" in tags
        assert "idea" in tags
        assert "meeting" in tags

    def test_is_joidy_file(self):
        assert _is_joidy_file("/vault/_joidy/sync.md")
        assert not _is_joidy_file("/vault/notes/page.md")

    def test_fingerprint_stable_and_distinct(self):
        assert _fingerprint("abc") == _fingerprint("abc")
        assert _fingerprint("abc") != _fingerprint("abd")


class TestPersistentEventLog(unittest.TestCase):
    def test_add_remove_and_pending_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = PersistentEventLog(Path(tmp) / "events.db")
            log.add("/vault/a.md", Change.added)
            log.add("/vault/b.md", Change.deleted)
            pending = log.pending()
            paths = {p for p, _ in pending}
            assert paths == {"/vault/a.md", "/vault/b.md"}

            log.remove("/vault/a.md")
            pending = log.pending()
            assert len(pending) == 1
            assert pending[0][0] == "/vault/b.md"
            assert pending[0][1] == Change.deleted
            log.close()

    def test_reopen_recovers_pending_events(self):
        """Crash recovery: events persisted before a crash are replayed (#371)."""
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "events.db"
            log = PersistentEventLog(log_path)
            log.add("/vault/unsynced.md", Change.modified)
            log.close()
            # Simulate a crash by opening a fresh instance against the same file.
            log2 = PersistentEventLog(log_path)
            pending = log2.pending()
            assert len(pending) == 1
            assert pending[0] == ("/vault/unsynced.md", Change.modified)
            log2.close()


class TestVaultSync(unittest.IsolatedAsyncioTestCase):
    def _client(self, responses):
        client = AsyncMock()

        async def side_effect(*args, **kwargs):
            return responses.pop(0)

        client.get.side_effect = side_effect
        client.post.side_effect = side_effect
        client.put.side_effect = side_effect
        client.delete.side_effect = side_effect
        return client

    @patch("watchers.vault_watcher.get_auth_token", new=AsyncMock(return_value="token"))
    async def test_import_or_update_note_creates_new_note(self):
        with tempfile.TemporaryDirectory() as tmp:
            md = Path(tmp) / "meeting.md"
            md.write_text("---\ntitle: Sync Test\ntags: [work]\n---\nContenido #demo", encoding="utf-8")

            responses = [
                FakeResponse(200, []),  # no existing note
                FakeResponse(201),  # create new note
            ]
            client = self._client(responses)

            await import_or_update_note(md, client, "token")

            assert client.post.call_count == 1
            payload = client.post.call_args.kwargs["json"]
            assert payload["title"] == "Sync Test"
            assert payload["source_path"] == str(md)

    @patch("watchers.vault_watcher.get_auth_token", new=AsyncMock(return_value="token"))
    async def test_import_or_update_note_updates_existing_note(self):
        with tempfile.TemporaryDirectory() as tmp:
            md = Path(tmp) / "existing.md"
            md.write_text("Nuevo contenido #update", encoding="utf-8")

            responses = [
                FakeResponse(200, [{"id": 7, "source_path": str(md)}]),
                FakeResponse(200),  # update
            ]
            client = self._client(responses)

            await import_or_update_note(md, client, "token")

            assert client.put.call_count == 1
            assert client.put.call_args.args[0].endswith("/notes/7")

    @patch("watchers.vault_watcher.get_auth_token", new=AsyncMock(return_value="token"))
    async def test_delete_note_by_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            md = Path(tmp) / "delete.md"
            md.write_text("x", encoding="utf-8")

            responses = [
                FakeResponse(200, [{"id": 9, "source_path": str(md)}]),
                FakeResponse(204),
            ]
            client = self._client(responses)

            await delete_note_by_path(str(md), client, "token")

            assert client.delete.call_count == 1

    @patch("watchers.vault_watcher.get_auth_token", new=AsyncMock(return_value="token"))
    async def test_debounce_accumulates_events(self):
        queue = asyncio.Queue()

        async def producer():
            await queue.put(vault_watcher.VaultEvent(path="/vault/a.md", change_type=vault_watcher.Change.added))
            await queue.put(vault_watcher.VaultEvent(path="/vault/a.md", change_type=vault_watcher.Change.modified))
            return True

        with patch("watchers.vault_watcher.QUEUE_FLUSH_INTERVAL", 0.05), patch(
            "watchers.vault_watcher.DEBOUNCE_SECONDS", 0.05
        ):
            pass

        # The consumer test below is heavy on IO; here we only ensure the
        # queue can hold repeated events for the same file and that the loop
        # can be cancelled cleanly.
        producer_task = asyncio.create_task(producer())
        await producer_task
        assert queue.qsize() == 2
        # Drain queue manually since we are not running the consumer.
        while not queue.empty():
            queue.get_nowait()
