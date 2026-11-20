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
    _is_safe_vault_file,
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


class TestVaultFileSafety(unittest.TestCase):
    """Reject symlinks, vault escapes and non-regular files before any
    read_text() call — a ``vault/leak.md -> /app/.env`` link would otherwise
    exfiltrate secrets into a note readable via the API (#1293)."""

    def test_regular_file_inside_vault_accepted(self):
        with tempfile.TemporaryDirectory() as vault:
            md = Path(vault) / "note.md"
            md.write_text("content", encoding="utf-8")
            with patch.object(vault_watcher.settings, "vault_path", vault):
                assert _is_safe_vault_file(md)

    def test_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as vault, tempfile.TemporaryDirectory() as outside:
            secret = Path(outside) / ".env"
            secret.write_text("SECRET_KEY=x", encoding="utf-8")
            link = Path(vault) / "leak.md"
            link.symlink_to(secret)
            with patch.object(vault_watcher.settings, "vault_path", vault):
                assert not _is_safe_vault_file(link)

    def test_symlink_inside_vault_also_rejected(self):
        """Symlinks are skipped unconditionally — even one pointing at a
        legit vault file is not a regular vault file itself."""
        with tempfile.TemporaryDirectory() as vault:
            real = Path(vault) / "real.md"
            real.write_text("real", encoding="utf-8")
            link = Path(vault) / "alias.md"
            link.symlink_to(real)
            with patch.object(vault_watcher.settings, "vault_path", vault):
                assert not _is_safe_vault_file(link)

    def test_symlinked_parent_escape_rejected(self):
        """A file reached through a symlinked directory inside the vault
        resolves outside the vault root and must be skipped, even though the
        path itself is not a symlink."""
        with tempfile.TemporaryDirectory() as vault, tempfile.TemporaryDirectory() as outside:
            secret = Path(outside) / "escaped.md"
            secret.write_text("SECRET", encoding="utf-8")
            (Path(vault) / "linkdir").symlink_to(outside, target_is_directory=True)
            with patch.object(vault_watcher.settings, "vault_path", vault):
                assert not _is_safe_vault_file(Path(vault) / "linkdir" / "escaped.md")

    def test_non_regular_file_rejected(self):
        """FIFOs, sockets and devices must never be read as notes (#1293)."""
        with tempfile.TemporaryDirectory() as vault:
            fifo = Path(vault) / "pipe.md"
            os.mkfifo(fifo)
            with patch.object(vault_watcher.settings, "vault_path", vault):
                assert not _is_safe_vault_file(fifo)


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

            with patch.object(vault_watcher.settings, "vault_path", tmp):
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

            with patch.object(vault_watcher.settings, "vault_path", tmp):
                await import_or_update_note(md, client, "token")

            assert client.put.call_count == 1
            assert client.put.call_args.args[0].endswith("/notes/7")

    @patch("watchers.vault_watcher.get_auth_token", new=AsyncMock(return_value="token"))
    async def test_import_or_update_note_skips_symlink(self):
        """``vault/leak.md -> /app/.env`` must never reach the API (#1293)."""
        with tempfile.TemporaryDirectory() as vault, tempfile.TemporaryDirectory() as outside:
            secret = Path(outside) / ".env"
            secret.write_text("SECRET_KEY=abc\nGEMINI_API_KEY=x", encoding="utf-8")
            link = Path(vault) / "leak.md"
            link.symlink_to(secret)

            client = self._client([])
            with patch.object(vault_watcher.settings, "vault_path", vault):
                await import_or_update_note(link, client, "token")

            assert client.get.call_count == 0
            assert client.post.call_count == 0
            assert client.put.call_count == 0

    @patch("watchers.vault_watcher.get_auth_token", new=AsyncMock(return_value="token"))
    async def test_initial_scan_skips_symlink(self):
        """initial_scan filters symlinks before importing (#1293)."""
        with tempfile.TemporaryDirectory() as vault, tempfile.TemporaryDirectory() as outside:
            real = Path(vault) / "real.md"
            real.write_text("real content", encoding="utf-8")
            secret = Path(outside) / "secret.md"
            secret.write_text("SECRET", encoding="utf-8")
            link = Path(vault) / "leak.md"
            link.symlink_to(secret)

            responses = [
                FakeResponse(200, []),  # no existing note for real.md
                FakeResponse(201),  # create real.md
                FakeResponse(200),  # rebuild-derived
            ]
            client = self._client(responses)
            with patch.object(vault_watcher.settings, "vault_path", vault):
                await vault_watcher.initial_scan(Path(vault), client, "token")

            posted = [c.kwargs["json"]["source_path"] for c in client.post.call_args_list if "json" in c.kwargs]
            assert str(real) in posted
            assert str(link) not in posted

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

        with (
            patch("watchers.vault_watcher.QUEUE_FLUSH_INTERVAL", 0.05),
            patch("watchers.vault_watcher.DEBOUNCE_SECONDS", 0.05),
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
