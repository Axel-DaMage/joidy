"""
Obsidian Vault Watcher

Monitors the vault directory for .md file changes (excluding _joidy/).
On change: imports the note via the API → triggers AI classification.

Uses debouncing: waits 2s after the last change to a file before processing,
to avoid reading files while Obsidian is still writing them.
"""

import asyncio
import hashlib
import logging
import re
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path

import httpx
from config import settings
from logging_config import get_correlation_id, set_correlation_id
from watchfiles import Change, awatch

logger = logging.getLogger(__name__)

JOIDY_DIR = "_joidy"
DEBOUNCE_SECONDS = 2.0
QUEUE_FLUSH_INTERVAL = 0.5
MAX_AUTH_RETRIES = 5
SHUTDOWN_TIMEOUT = 15.0  # seconds to let in-flight writes finish on shutdown


@dataclass(frozen=True)
class VaultEvent:
    path: str
    change_type: Change


_auth_token: str = ""
_auth_lock = asyncio.Lock()

# Per-file locks so rapid successive edits to the same file cannot start
# concurrent imports for that file (#364).
_file_locks: dict[str, asyncio.Lock] = {}
_file_locks_guard = asyncio.Lock()

# Last-synced content fingerprint per path, used to detect renames: a deleted
# file whose hash matches an added file in the same batch is a move, not a
# delete+create (#364).
_fingerprints: dict[str, str] = {}

# Set by the worker's signal handler to trigger a graceful two-phase shutdown:
# stop accepting new filesystem events, then let in-flight writes finish (#371).
shutdown_event: asyncio.Event = asyncio.Event()


async def _get_file_lock(path: str) -> asyncio.Lock:
    async with _file_locks_guard:
        lock = _file_locks.get(path)
        if lock is None:
            lock = asyncio.Lock()
            _file_locks[path] = lock
        return lock


def _fingerprint(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()


class PersistentEventLog:
    """SQLite-backed log of pending vault events.

    Events are recorded before processing and removed once the batch succeeds,
    so if the worker crashes mid-processing the events are replayed on the next
    startup (#371). The log keys on path (last write wins), mirroring the
    in-memory batch dedup.
    """

    def __init__(self, path: str):
        self._path = path
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(path, check_same_thread=False)
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS pending_events "
                "(path TEXT PRIMARY KEY, change_type TEXT NOT NULL)"
            )
            self._conn.commit()
        except Exception as exc:
            logger.warning("[vault] Persistent event log unavailable (%s); "
                           "crash recovery disabled", exc)
            self._conn = None

    def add(self, path: str, change_type: Change) -> None:
        if self._conn is None:
            return
        try:
            self._conn.execute(
                "INSERT OR REPLACE INTO pending_events (path, change_type) VALUES (?, ?)",
                (path, change_type.name),
            )
            self._conn.commit()
        except Exception as exc:
            logger.warning("[vault] Failed to persist event %s: %s", path, exc)

    def remove(self, path: str) -> None:
        if self._conn is None:
            return
        try:
            self._conn.execute("DELETE FROM pending_events WHERE path = ?", (path,))
            self._conn.commit()
        except Exception as exc:
            logger.warning("[vault] Failed to remove event %s: %s", path, exc)

    def pending(self) -> list[tuple[str, Change]]:
        if self._conn is None:
            return []
        try:
            rows = self._conn.execute(
                "SELECT path, change_type FROM pending_events"
            ).fetchall()
            result = []
            for path, ct_name in rows:
                try:
                    result.append((path, Change[ct_name]))
                except KeyError:
                    # Unknown change type from an older log version — drop it.
                    self._conn.execute(
                        "DELETE FROM pending_events WHERE path = ?", (path,)
                    )
            self._conn.commit()
            return result
        except Exception as exc:
            logger.warning("[vault] Failed to read pending events: %s", exc)
            return []

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None


async def get_auth_token(client: httpx.AsyncClient, *, force: bool = False) -> str:
    """Get or refresh the API auth token with retries.

    Caches the token locally. Use `force=True` to bypass the cache and fetch a
    new token, e.g. after a 401 response.
    """
    global _auth_token

    if not settings.auth_password:
        return ""

    async with _auth_lock:
        if not force and _auth_token:
            return _auth_token

        for attempt in range(MAX_AUTH_RETRIES):
            try:
                cid = get_correlation_id()
                r = await client.post(
                    f"{settings.api_url}/auth/login",
                    json={"password": settings.auth_password},
                    headers={"X-Request-ID": cid},
                    timeout=10.0,
                )
                if r.status_code == 200:
                    _auth_token = r.json().get("access_token", "")
                    if _auth_token:
                        logger.info("[vault] Auth token refreshed")
                        return _auth_token
                    logger.warning("[vault] Auth response missing access_token")
                else:
                    logger.warning("[vault] Auth login returned %s", r.status_code)
            except Exception as e:
                logger.error("[vault] Failed to get auth token (attempt %d/%d): %s", attempt + 1, MAX_AUTH_RETRIES, e)

            if attempt < MAX_AUTH_RETRIES - 1:
                wait = min(2 ** attempt, 30.0)
                logger.info("[vault] Retrying auth in %.1fs", wait)
                await asyncio.sleep(wait)

        _auth_token = ""
        return ""

def _is_joidy_file(path: str) -> bool:
    return JOIDY_DIR in Path(path).parts


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    """Extract YAML frontmatter and body from markdown."""
    frontmatter = {}
    body = content
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            fm_text = content[3:end].strip()
            body = content[end + 3:].strip()
            for line in fm_text.splitlines():
                if ":" in line:
                    key, _, value = line.partition(":")
                    frontmatter[key.strip()] = value.strip()
    return frontmatter, body


def _extract_tags_from_content(content: str, frontmatter: dict) -> list[str]:
    """Extract tags from frontmatter and inline #tags."""
    tags = []
    # Frontmatter tags
    if "tags" in frontmatter:
        raw = frontmatter["tags"].strip("[]")
        tags.extend([t.strip() for t in raw.split(",") if t.strip()])
    # Inline #tags
    inline = re.findall(r"#([a-zA-Z][a-zA-Z0-9_-]+)", content)
    tags.extend(inline)
    return list(set(t.lower() for t in tags if t))


async def delete_note_by_path(path: str, client: httpx.AsyncClient, token: str):
    """Find and delete a note by its source_path with retries."""
    for attempt in range(3):
        try:
            current_token = await get_auth_token(client)
            cid = get_correlation_id()
            headers = {"X-Request-ID": cid}
            if current_token:
                headers["Authorization"] = f"Bearer {current_token}"
            r = await client.get(f"{settings.api_url}/notes/", params={"source_path": path}, headers=headers, timeout=10.0)
            if r.status_code == 401:
                logger.warning("[vault] Auth expired while deleting %s, refreshing token", Path(path).name)
                await get_auth_token(client, force=True)
                continue
            if r.status_code == 200:
                notes = r.json()
                for n in notes:
                    if n.get("source_path") == path:
                        del_res = await client.delete(f"{settings.api_url}/notes/{n['id']}", headers=headers, timeout=10.0)
                        if del_res.status_code == 401:
                            await get_auth_token(client, force=True)
                            continue
                        logger.info("[vault] Deleted: %s", Path(path).name)
                        return
            break # Success or not found
        except Exception as e:
            if attempt == 2:
                logger.exception("[vault] Error deleting %s: %s", path, e)
            await asyncio.sleep(1 * (attempt + 1))


async def rename_note_path(old_path: str, new_path: Path, client: httpx.AsyncClient, token: str):
    """Treat a delete+add pair as a rename: update the existing note's
    source_path instead of deleting and recreating it, preserving id/XP/history
    (#364)."""
    try:
        if not new_path.exists():
            return
        content = new_path.read_text(encoding="utf-8", errors="replace")
        frontmatter, body = _parse_frontmatter(content)
        title = frontmatter.get("title") or new_path.stem.replace("-", " ").replace("_", " ").title()
        tags = _extract_tags_from_content(content, frontmatter)

        # Find the existing note by the OLD source_path.
        existing = None
        for attempt in range(3):
            try:
                current_token = await get_auth_token(client)
                cid = get_correlation_id()
                headers = {"X-Request-ID": cid}
                if current_token:
                    headers["Authorization"] = f"Bearer {current_token}"
                r = await client.get(
                    f"{settings.api_url}/notes/",
                    params={"source_path": old_path},
                    headers=headers,
                    timeout=10.0,
                )
                if r.status_code == 401:
                    await get_auth_token(client, force=True)
                    continue
                if r.status_code == 200:
                    for n in r.json():
                        if n.get("source_path") == old_path:
                            existing = n
                            break
                break
            except Exception:
                if attempt == 2:
                    raise
                await asyncio.sleep(1)

        if not existing:
            # No note at the old path — fall back to a normal import of the new path.
            await import_or_update_note(new_path, client, token)
            return

        for attempt in range(5):
            current_token = await get_auth_token(client)
            cid = get_correlation_id()
            headers = {"X-Request-ID": cid, "X-From-Vault": "1"}
            if current_token:
                headers["Authorization"] = f"Bearer {current_token}"
            res = await client.put(
                f"{settings.api_url}/notes/{existing['id']}",
                json={"title": title, "content": content, "tags": tags,
                      "source": "obsidian", "source_path": str(new_path)},
                headers=headers,
                timeout=10.0,
            )
            if res.status_code == 401:
                await get_auth_token(client, force=True)
                continue
            if res.status_code in (429, 500, 503):
                await asyncio.sleep(2 ** attempt)
                continue
            res.raise_for_status()
            _fingerprints[str(new_path)] = _fingerprint(content)
            _fingerprints.pop(old_path, None)
            logger.info("[vault] Renamed: %s -> %s", Path(old_path).name, new_path.name)
            return
    except Exception as e:
        logger.exception("[vault] Error renaming %s -> %s: %s", old_path, new_path, e)


async def import_or_update_note(filepath: Path, client: httpx.AsyncClient, token: str, *, bulk_import: bool = False):
    try:
        if not filepath.exists():
            return
        content = filepath.read_text(encoding="utf-8", errors="replace")
        frontmatter, body = _parse_frontmatter(content)
        title = frontmatter.get("title") or filepath.stem.replace("-", " ").replace("_", " ").title()
        tags = _extract_tags_from_content(content, frontmatter)

        # Check if note already exists by source_path (with retry + auth refresh)
        existing = None
        for attempt in range(3):
            try:
                current_token = await get_auth_token(client)
                cid = get_correlation_id()
                headers = {"X-Request-ID": cid}
                if current_token:
                    headers["Authorization"] = f"Bearer {current_token}"
                r = await client.get(
                    f"{settings.api_url}/notes/",
                    params={"source_path": str(filepath)},
                    headers=headers,
                    timeout=10.0,
                )
                if r.status_code == 401:
                    logger.warning("[vault] Auth expired while checking %s, refreshing token", filepath.name)
                    await get_auth_token(client, force=True)
                    continue
                if r.status_code == 200:
                    notes = r.json()
                    for n in notes:
                        if n.get("source_path") == str(filepath):
                            existing = n
                            break
                break
            except Exception:
                if attempt == 2: raise
                await asyncio.sleep(1)

        payload = {"title": title, "content": content, "tags": tags, "source": "obsidian", "source_path": str(filepath)}

        for attempt in range(5):
            current_token = await get_auth_token(client)
            cid = get_correlation_id()
            headers = {"X-Request-ID": cid, "X-From-Vault": "1"}
            if bulk_import:
                headers["X-Bulk-Import"] = "1"
            if current_token:
                headers["Authorization"] = f"Bearer {current_token}"

            if existing:
                res = await client.put(
                    f"{settings.api_url}/notes/{existing['id']}",
                    json={"title": title, "content": content, "tags": tags, "source": "obsidian", "source_path": str(filepath)},
                    headers=headers,
                    timeout=10.0,
                )
            else:
                res = await client.post(f"{settings.api_url}/notes/", json=payload, headers=headers, timeout=10.0)

            if res.status_code == 401:
                logger.warning("[vault] Auth expired while syncing %s, refreshing token", filepath.name)
                await get_auth_token(client, force=True)
                continue

            if res.status_code in (429, 500, 503):
                wait = 2 ** attempt
                logger.warning("[vault] %s syncing %s (attempt %d/%d), retrying in %ss", res.status_code, filepath.name, attempt + 1, 5, wait)
                await asyncio.sleep(wait)
                continue

            res.raise_for_status()
            break

        _fingerprints[str(filepath)] = _fingerprint(content)
        logger.info("[vault] Synced: %s", filepath.name)

    except Exception as e:
        logger.exception("[vault] Error syncing %s: %s", filepath, e)


async def initial_scan(vault_path: Path, client: httpx.AsyncClient, token: str):
    """On startup, import all .md files not in _joidy/."""
    md_files = [p for p in vault_path.rglob("*.md") if not _is_joidy_file(str(p))]
    logger.info("[vault] Initial scan: %s markdown files found", len(md_files))

    semaphore = asyncio.Semaphore(4)

    async def process_file(filepath: Path):
        async with semaphore:
            await import_or_update_note(filepath, client, token, bulk_import=True)

    await asyncio.gather(*(process_file(filepath) for filepath in md_files), return_exceptions=True)

    for attempt in range(2):
        current_token = await get_auth_token(client)
        headers = {"X-Request-ID": get_correlation_id()}
        if current_token:
            headers["Authorization"] = f"Bearer {current_token}"
        r = await client.post(f"{settings.api_url}/notes/rebuild-derived", headers=headers, timeout=30.0)
        if r.status_code == 401:
            logger.warning("[vault] Auth expired while rebuilding derived, refreshing token")
            await get_auth_token(client, force=True)
            continue
        r.raise_for_status()
        break


async def _consume_vault_events(
    queue: asyncio.Queue[VaultEvent],
    client: httpx.AsyncClient,
    token: str,
    event_log: PersistentEventLog,
):
    _in_flight: set[asyncio.Task] = set()
    while True:
        if shutdown_event.is_set():
            # Graceful shutdown phase 2: stop taking new batches, but let any
            # in-flight writes finish (handled below) before returning.
            return
        try:
            try:
                first_event = await asyncio.wait_for(queue.get(), timeout=1.0)
            except TimeoutError:
                continue
            pending: dict[str, Change] = {first_event.path: first_event.change_type}

            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=QUEUE_FLUSH_INTERVAL)
                    pending[event.path] = event.change_type
                except TimeoutError:
                    break

            await asyncio.sleep(DEBOUNCE_SECONDS)

            # Rename detection (#364): pair a deleted path with an added path
            # whose content fingerprint matches the last-seen content of the
            # deleted path. Treat the pair as a move (update source_path) and
            # drop both from the delete/add processing.
            deletes: dict[str, Change] = {}
            adds: dict[str, Change] = {}
            for path, ct in pending.items():
                if ct == Change.deleted:
                    deletes[path] = ct
                else:
                    adds[path] = ct

            renames: list[tuple[str, str]] = []  # (old_path, new_path)
            consumed_adds: set[str] = set()
            for old_path in list(deletes.keys()):
                old_fp = _fingerprints.get(old_path)
                if not old_fp:
                    continue
                for new_path in adds:
                    if new_path in consumed_adds:
                        continue
                    try:
                        if Path(new_path).exists():
                            content = Path(new_path).read_text(encoding="utf-8", errors="replace")
                            if _fingerprint(content) == old_fp:
                                renames.append((old_path, new_path))
                                consumed_adds.add(new_path)
                                break
                    except Exception:
                        continue

            for old_path, new_path in renames:
                deletes.pop(old_path, None)
                pending.pop(old_path, None)
                pending.pop(new_path, None)

            remaining = {**deletes}
            for path, ct in adds.items():
                if path not in consumed_adds:
                    remaining[path] = ct

            async def process(path: str, change_type: Change):
                lock = await _get_file_lock(path)
                async with lock:
                    try:
                        # Shield the critical write so a shutdown cancellation
                        # does not interrupt a mid-flight API call (#371).
                        if change_type == Change.deleted:
                            await asyncio.shield(delete_note_by_path(path, client, token))
                        else:
                            await asyncio.shield(import_or_update_note(Path(path), client, token))
                        event_log.remove(path)
                    except asyncio.CancelledError:
                        # Propagate cancellation but keep the event logged so
                        # it is retried on the next startup.
                        raise
                    except Exception:
                        logger.exception("[vault] Failed to process %s (%s)", path, change_type)

            async def process_rename(old_path: str, new_path: str):
                lock = await _get_file_lock(old_path)
                async with lock:
                    try:
                        await asyncio.shield(rename_note_path(old_path, Path(new_path), client, token))
                        event_log.remove(old_path)
                        event_log.remove(new_path)
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        logger.exception("[vault] Failed to rename %s -> %s", old_path, new_path)

            batch_tasks: list[asyncio.Task] = []
            for old_path, new_path in renames:
                batch_tasks.append(asyncio.ensure_future(process_rename(old_path, new_path)))
            for path, change_type in remaining.items():
                batch_tasks.append(asyncio.ensure_future(process(path, change_type)))

            _in_flight.update(batch_tasks)
            await asyncio.gather(*batch_tasks, return_exceptions=True)
            _in_flight.difference_update(batch_tasks)
        except asyncio.CancelledError:
            # Hard cancellation (e.g. timeout after graceful phase). Let any
            # in-flight tasks finish that can; cancel the rest.
            for task in _in_flight:
                if not task.done():
                    task.cancel()
            if _in_flight:
                await asyncio.gather(*_in_flight, return_exceptions=True)
                logger.info("[vault] Cancelled %d in-flight task(s) on shutdown", len(_in_flight))
            return
        except Exception:
            logger.exception("[vault] Unexpected error in event consumer")
            await asyncio.sleep(1)  # Prevent tight error loop


async def watch_vault():
    set_correlation_id(f"worker-{uuid.uuid4().hex[:12]}")
    vault_path = Path(settings.vault_path)
    if not vault_path.exists():
        logger.warning("[vault] Vault path %s does not exist - skipping file watch", vault_path)
        return

    logger.info("[vault] Watching: %s", vault_path)

    event_log = PersistentEventLog(settings.event_log_path)
    async with httpx.AsyncClient(timeout=30.0) as client:
        consumer = None
        try:
            token = await get_auth_token(client)
            if settings.auth_password and not token:
                logger.error("[vault] Could not get auth token; aborting vault sync")
                return
            await initial_scan(vault_path, client, token)

            queue: asyncio.Queue[VaultEvent] = asyncio.Queue(maxsize=1000)

            # Replay events that were persisted but not processed before a
            # previous crash (#371).
            pending = event_log.pending()
            if pending:
                logger.info("[vault] Recovering %d pending event(s) from previous run", len(pending))
                for path, change_type in pending:
                    await queue.put(VaultEvent(path=path, change_type=change_type))

            consumer = asyncio.create_task(
                _consume_vault_events(queue, client, token, event_log),
                name="vault_event_consumer",
            )

            max_retries = 5
            retry_delay = 1.0
            for attempt in range(max_retries):
                try:
                    async for changes in awatch(str(vault_path)):
                        if shutdown_event.is_set():
                            break
                        retry_delay = 1.0
                        for change_type, path in changes:
                            if not path.endswith(".md"):
                                continue
                            if _is_joidy_file(path):
                                continue
                            event_log.add(path, change_type)
                            await queue.put(VaultEvent(path=path, change_type=change_type))
                    break
                except Exception as e:
                    if shutdown_event.is_set():
                        break
                    logger.error("[vault] Watcher error (attempt %d/%d): %s", attempt + 1, max_retries, e)
                    if attempt == max_retries - 1:
                        raise
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, 60.0)

            # Graceful shutdown phase 1 is already done (awatch stopped
            # accepting). Phase 2: let the consumer drain the queue and finish
            # in-flight writes, then return.
            if consumer is not None:
                try:
                    await asyncio.wait_for(consumer, timeout=SHUTDOWN_TIMEOUT)
                except (TimeoutError, asyncio.CancelledError):
                    logger.warning("[vault] Consumer did not finish within %.0fs; cancelling", SHUTDOWN_TIMEOUT)
                    consumer.cancel()
                    try:
                        await consumer
                    except (asyncio.CancelledError, Exception):
                        pass
        finally:
            event_log.close()
            logger.info("[vault] Watcher stopped cleanly")
