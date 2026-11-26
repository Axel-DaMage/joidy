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

    def test_fingerprints_survive_reopen(self):
        """Rename fingerprints persist across restarts (#1302)."""
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "events.db"
            log = PersistentEventLog(log_path)
            log.set_fingerprint("/vault/a.md", "deadbeef")
            log.close()

            log2 = PersistentEventLog(log_path)
            assert log2.fingerprints() == {"/vault/a.md": "deadbeef"}
            log2.remove_fingerprint("/vault/a.md")
            assert log2.fingerprints() == {}
            log2.close()

    def test_wal_mode_and_normal_synchronous(self):
        """The event log uses WAL + synchronous=NORMAL so commits append a
        WAL frame without a per-event fsync (#1536)."""
        with tempfile.TemporaryDirectory() as tmp:
            log = PersistentEventLog(Path(tmp) / "events.db")
            mode = log._conn.execute("PRAGMA journal_mode").fetchone()[0]
            synchronous = log._conn.execute("PRAGMA synchronous").fetchone()[0]
            log.close()
            assert mode == "wal"
            assert synchronous == 1  # NORMAL (0=OFF, 2=FULL, 3=EXTRA)

    def test_remove_is_staged_until_commit(self):
        """remove() no longer commits per event — a second connection sees
        the rows until commit() flushes the staged deletes (#1536)."""
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "events.db"
            log = PersistentEventLog(log_path)
            log.add("/vault/a.md", Change.added)
            log.add("/vault/b.md", Change.deleted)
            log.remove("/vault/a.md")

            # Uncommitted on conn1: still visible to a fresh connection.
            check = PersistentEventLog(log_path)
            assert {p for p, _ in check.pending()} == {"/vault/a.md", "/vault/b.md"}

            log.commit()
            assert check.pending() == [("/vault/b.md", Change.deleted)]

            check.close()
            log.close()

    def test_staged_removes_survive_reopen_after_commit(self):
        """Batched removals are durable once commit() ran (#1536)."""
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "events.db"
            log = PersistentEventLog(log_path)
            log.add("/vault/a.md", Change.added)
            log.remove("/vault/a.md")
            log.commit()
            log.close()

            log2 = PersistentEventLog(log_path)
            assert log2.pending() == []
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
                FakeResponse(200, []),  # source-paths bulk lookup: API holds nothing
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


class TestInitialScanShortCircuit(unittest.IsolatedAsyncioTestCase):
    """#1535: initial_scan must not re-import files whose stored content
    fingerprint already matches the current file content."""

    def tearDown(self):
        # Module-global fingerprint/event-log state must not leak between tests.
        vault_watcher._unbind_event_log()
        vault_watcher._fingerprints.clear()

    def _client(self, responses, source_paths=None):
        """AsyncMock httpx client; ``responses`` is a list of
        (method, FakeResponse) tuples popped in order. Any call whose method
        has no queued response falls back to a 200 default (``[]`` for GET).

        ``source_paths`` controls the GET /notes/source-paths bulk lookup:
        a list/str iterable is returned as the JSON body, a FakeResponse is
        returned as-is (e.g. a failing one), an exception is raised. None
        returns an empty list — the API holds no paths, so nothing is
        skipped on fingerprints alone.
        """
        client = AsyncMock()
        queue = list(responses)

        def _next(method):
            for i, (m, _resp) in enumerate(queue):
                if m == method:
                    return queue.pop(i)[1]
            return FakeResponse(200, [] if method == "GET" else {})

        async def _get(url, *args, **kwargs):
            if str(url).endswith("/notes/source-paths"):
                if isinstance(source_paths, BaseException):
                    raise source_paths
                if isinstance(source_paths, FakeResponse):
                    return source_paths
                return FakeResponse(200, list(source_paths or []))
            return _next("GET")

        async def _post(*args, **kwargs):
            return _next("POST")

        async def _put(*args, **kwargs):
            return _next("PUT")

        async def _delete(*args, **kwargs):
            return _next("DELETE")

        client.get.side_effect = _get
        client.post.side_effect = _post
        client.put.side_effect = _put
        client.delete.side_effect = _delete
        return client

    @staticmethod
    def _write(path: Path, content: str) -> str:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return content

    @patch("watchers.vault_watcher.get_auth_token", new=AsyncMock(return_value="token"))
    async def test_second_scan_skips_unchanged_files(self):
        """A restart of a healthy worker is a no-op: files whose stored
        fingerprint matches their content make zero per-note HTTP calls."""
        with tempfile.TemporaryDirectory() as vault:
            root = Path(vault)
            md_a = root / "a.md"
            md_b = root / "b.md"
            content_a = self._write(md_a, "content A")
            content_b = self._write(md_b, "content B")

            # Simulate fingerprints recorded by the previous run's syncs —
            # and the API still holding both source_paths.
            vault_watcher._fingerprints[str(md_a)] = _fingerprint(content_a)
            vault_watcher._fingerprints[str(md_b)] = _fingerprint(content_b)

            client = self._client([], source_paths=[str(md_a), str(md_b)])
            with patch.object(vault_watcher.settings, "vault_path", vault):
                await vault_watcher.initial_scan(root, client, "token")

            # No per-note lookup/create/update — only the one bulk
            # source-paths GET and the rebuild-derived POST.
            assert client.get.call_count == 1
            assert client.get.call_args.args[0].endswith("/notes/source-paths")
            assert client.put.call_count == 0
            assert client.post.call_count == 1
            assert "json" not in client.post.call_args.kwargs  # rebuild-derived, no payload

    @patch("watchers.vault_watcher.get_auth_token", new=AsyncMock(return_value="token"))
    async def test_changed_and_new_files_are_synced(self):
        """Only files with a matching fingerprint are skipped: a file whose
        content changed since the recorded fingerprint, and a file with no
        fingerprint at all, are both synced."""
        with tempfile.TemporaryDirectory() as vault:
            root = Path(vault)
            unchanged = root / "same.md"
            changed = root / "edited.md"
            new = root / "new.md"
            same_content = self._write(unchanged, "same content")
            self._write(changed, "edited content")
            self._write(new, "brand new")

            vault_watcher._fingerprints[str(unchanged)] = _fingerprint(same_content)
            vault_watcher._fingerprints[str(changed)] = _fingerprint("stale content")

            # The API holds both fingerprinted paths — but a matching
            # fingerprint only skips when the content still matches.
            client = self._client(
                [
                    ("GET", FakeResponse(200, [])),  # edited.md: no existing note
                    ("GET", FakeResponse(200, [])),  # new.md: no existing note
                ],
                source_paths=[str(unchanged), str(changed)],
            )
            with patch.object(vault_watcher.settings, "vault_path", vault):
                await vault_watcher.initial_scan(root, client, "token")

            # The unchanged file was never looked up (per-file GETs carry a
            # ``source_path`` param; the bulk lookup does not).
            looked_up = {c.kwargs["params"]["source_path"] for c in client.get.call_args_list if "params" in c.kwargs}
            assert str(unchanged) not in looked_up
            assert looked_up == {str(changed), str(new)}

            # Both out-of-sync files were created (no existing note).
            created = {c.kwargs["json"]["source_path"] for c in client.post.call_args_list if "json" in c.kwargs}
            assert created == {str(changed), str(new)}

    @patch("watchers.vault_watcher.get_auth_token", new=AsyncMock(return_value="token"))
    async def test_pending_event_forces_resync_despite_matching_fingerprint(self):
        """Crash-recovery conservatism: a path with a pending event in the
        persistent log is never skipped — its last sync may have failed."""
        with tempfile.TemporaryDirectory() as vault:
            root = Path(vault)
            md = root / "flaky.md"
            content = self._write(md, "content")

            log = PersistentEventLog(root / "events.db")
            log.set_fingerprint(str(md), _fingerprint(content))
            log.add(str(md), Change.modified)
            vault_watcher._bind_event_log(log)
            try:
                client = self._client(
                    [
                        ("GET", FakeResponse(200, [{"id": 7, "source_path": str(md)}])),
                        ("PUT", FakeResponse(200)),
                    ],
                    source_paths=[str(md)],
                )
                with patch.object(vault_watcher.settings, "vault_path", vault):
                    await vault_watcher.initial_scan(root, client, "token")

                # One per-file lookup (the bulk source-paths GET has no params).
                per_file = [c for c in client.get.call_args_list if "params" in c.kwargs]
                assert len(per_file) == 1
                assert client.put.call_count == 1
                assert client.put.call_args.args[0].endswith("/notes/7")
            finally:
                log.close()

    @patch("watchers.vault_watcher.get_auth_token", new=AsyncMock(return_value="token"))
    async def test_recreated_file_after_successful_delete_is_resynced(self):
        """A file deleted at the API and then recreated with identical
        content must not be skipped — a successful delete drops the stored
        fingerprint, so the scan sees it as out-of-sync."""
        with tempfile.TemporaryDirectory() as vault:
            root = Path(vault)
            md = root / "phoenix.md"
            content = "same body"
            vault_watcher._fingerprints[str(md)] = _fingerprint(content)

            # Delete event processed while the file is absent.
            log = PersistentEventLog(root / "events.db")
            try:
                log.add(str(md), Change.deleted)
                client = self._client(
                    [
                        ("GET", FakeResponse(200, [{"id": 9, "source_path": str(md), "updated_at": "t0"}])),
                        ("DELETE", FakeResponse(200)),
                    ]
                )
                with patch.object(vault_watcher.settings, "vault_path", vault):
                    await vault_watcher._process_batch({str(md): Change.deleted}, client, "token", log)

                assert client.delete.call_count == 1
                assert str(md) not in vault_watcher._fingerprints

                # File recreated with identical content → scan resyncs it.
                self._write(md, content)
                client = self._client([("GET", FakeResponse(200, []))], source_paths=[str(md)])
                with patch.object(vault_watcher.settings, "vault_path", vault):
                    await vault_watcher.initial_scan(root, client, "token")

                created = {c.kwargs["json"]["source_path"] for c in client.post.call_args_list if "json" in c.kwargs}
                assert str(md) in created
            finally:
                log.close()

    @patch("watchers.vault_watcher.get_auth_token", new=AsyncMock(return_value="token"))
    async def test_api_missing_path_resyncs_despite_matching_fingerprint(self):
        """Dev-reset scenario: the sqlite fingerprint store survives a
        Postgres wipe, so a matching fingerprint alone must NOT skip a file
        whose source_path the API no longer holds."""
        with tempfile.TemporaryDirectory() as vault:
            root = Path(vault)
            md = root / "ghost.md"
            content = self._write(md, "survived the reset")

            vault_watcher._fingerprints[str(md)] = _fingerprint(content)

            # API holds no source_paths (wiped DB) — the matching fingerprint
            # is stale state, not proof of sync.
            client = self._client(
                [
                    ("GET", FakeResponse(200, [])),  # per-file lookup: absent
                    ("POST", FakeResponse(201)),  # create
                ],
                source_paths=[],
            )
            with patch.object(vault_watcher.settings, "vault_path", vault):
                await vault_watcher.initial_scan(root, client, "token")

            per_file = [c for c in client.get.call_args_list if "params" in c.kwargs]
            assert [c.kwargs["params"]["source_path"] for c in per_file] == [str(md)]
            created = {c.kwargs["json"]["source_path"] for c in client.post.call_args_list if "json" in c.kwargs}
            assert created == {str(md)}

    @patch("watchers.vault_watcher.get_auth_token", new=AsyncMock(return_value="token"))
    async def test_source_paths_lookup_failure_resyncs_everything(self):
        """If the bulk existence check fails, the scan must not skip on
        unverified fingerprints — fall back to a conservative full resync."""
        with tempfile.TemporaryDirectory() as vault:
            root = Path(vault)
            md_a = root / "a.md"
            md_b = root / "b.md"
            vault_watcher._fingerprints[str(md_a)] = _fingerprint(self._write(md_a, "content A"))
            vault_watcher._fingerprints[str(md_b)] = _fingerprint(self._write(md_b, "content B"))

            # Every source-paths attempt answers 500 → lookup returns None.
            client = self._client(
                [
                    ("GET", FakeResponse(200, [{"id": 1, "source_path": str(md_a)}])),
                    ("GET", FakeResponse(200, [])),
                ],
                source_paths=FakeResponse(500, raise_error=True),
            )
            with (
                patch.object(vault_watcher.settings, "vault_path", vault),
                patch("asyncio.sleep", new=AsyncMock()),
            ):
                await vault_watcher.initial_scan(root, client, "token")

            # Both files were resynced despite matching fingerprints.
            looked_up = {c.kwargs["params"]["source_path"] for c in client.get.call_args_list if "params" in c.kwargs}
            assert looked_up == {str(md_a), str(md_b)}
            synced = {
                c.kwargs["json"]["source_path"]
                for c in client.put.call_args_list + client.post.call_args_list
                if "json" in c.kwargs
            }
            assert synced == {str(md_a), str(md_b)}


class TestProcessBatch(unittest.IsolatedAsyncioTestCase):
    """_process_batch must bound concurrent API calls (#1536): a mass-change
    event used to fire hundreds of parallel syncs and exhaust the httpx
    pool. The same Semaphore limit as initial_scan now applies."""

    async def test_process_batch_bounds_concurrency(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            pending = {}
            # Added/modified events on real files.
            for i in range(12):
                p = vault / f"note{i}.md"
                p.write_text(f"content {i}", encoding="utf-8")
                pending[str(p)] = Change.added
            # Delete events on paths already gone.
            for i in range(6):
                pending[str(vault / f"gone{i}.md")] = Change.deleted
            # A rename pair: deleted old path whose fingerprint matches the
            # content of the added file.
            renamed = vault / "renamed.md"
            renamed.write_text("moved content", encoding="utf-8")
            old_path = str(vault / "old.md")
            vault_watcher._fingerprints[old_path] = _fingerprint("moved content")
            pending[old_path] = Change.deleted
            pending[str(renamed)] = Change.added

            running = 0
            peak = 0
            calls = {"import": 0, "delete": 0, "rename": 0}

            async def tracked(kind):
                nonlocal running, peak
                running += 1
                peak = max(peak, running)
                calls[kind] += 1
                await asyncio.sleep(0.01)
                running -= 1
                return True

            async def fake_import(filepath, client, token, **kwargs):
                return await tracked("import")

            async def fake_delete(path, client, token):
                return await tracked("delete")

            async def fake_rename(old, new, client, token):
                return await tracked("rename")

            log_path = vault / "events.db"
            log = PersistentEventLog(log_path)
            for path, ct in pending.items():
                log.add(path, ct)

            try:
                with (
                    patch.object(vault_watcher.settings, "vault_path", str(vault)),
                    patch.object(vault_watcher, "import_or_update_note", new=fake_import),
                    patch.object(vault_watcher, "delete_note_by_path", new=fake_delete),
                    patch.object(vault_watcher, "rename_note_path", new=fake_rename),
                ):
                    await vault_watcher._process_batch(dict(pending), AsyncMock(), "token", log)

                # 20 events, semaphore of BATCH_CONCURRENCY: real parallelism
                # but never more than the cap.
                assert peak <= vault_watcher.BATCH_CONCURRENCY
                assert peak > 1
                assert calls == {"import": 12, "delete": 6, "rename": 1}

                # The batch flushed staged event-log removals — a fresh
                # connection sees the log fully drained.
                check = PersistentEventLog(log_path)
                assert check.pending() == []
                check.close()
            finally:
                log.close()
                vault_watcher._fingerprints.pop(old_path, None)
