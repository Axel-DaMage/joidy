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

import auth as shared_auth
import httpx
from config import settings
from logging_config import get_correlation_id, set_correlation_id
from watchfiles import Change, awatch

logger = logging.getLogger(__name__)

JOIDY_DIR = "_joidy"
DEBOUNCE_SECONDS = 2.0
QUEUE_FLUSH_INTERVAL = 0.5
SHUTDOWN_TIMEOUT = 15.0  # seconds to let in-flight writes finish on shutdown


@dataclass(frozen=True)
class VaultEvent:
    path: str
    change_type: Change


# Per-file locks so rapid successive edits to the same file cannot start
# concurrent imports for that file (#364).
_file_locks: dict[str, asyncio.Lock] = {}
_file_locks_guard = asyncio.Lock()

# Last-synced content fingerprint per path, used to detect renames: a deleted
# file whose hash matches an added file in the same batch is a move, not a
# delete+create (#364). Fingerprints are also written through to the
# persistent event log (see _record_fingerprint) so rename detection still
# works when a delete+add pair spans a worker restart (#1302).
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

    The same DB also persists content fingerprints (path → sha256 of the
    last-synced content), so a delete+add pair spanning a restart can still
    be recognised as a rename and keep the note id/XP/history (#1302).
    """

    def __init__(self, path: str):
        self._path = path
        self._conn: sqlite3.Connection | None
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(path, check_same_thread=False)
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS pending_events (path TEXT PRIMARY KEY, change_type TEXT NOT NULL)"
            )
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS fingerprints (path TEXT PRIMARY KEY, fingerprint TEXT NOT NULL)"
            )
            self._conn.commit()
        except Exception as exc:
            # Exception type only — str(exc) can embed filesystem paths (#1299).
            logger.warning("[vault] Persistent event log unavailable (%s); crash recovery disabled", type(exc).__name__)
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
            logger.warning("[vault] Failed to persist event %s: %s", _log_name(path), type(exc).__name__)

    def remove(self, path: str) -> None:
        if self._conn is None:
            return
        try:
            self._conn.execute("DELETE FROM pending_events WHERE path = ?", (path,))
            self._conn.commit()
        except Exception as exc:
            logger.warning("[vault] Failed to remove event %s: %s", _log_name(path), type(exc).__name__)

    def pending(self) -> list[tuple[str, Change]]:
        if self._conn is None:
            return []
        try:
            rows = self._conn.execute("SELECT path, change_type FROM pending_events").fetchall()
            result = []
            for path, ct_name in rows:
                try:
                    result.append((path, Change[ct_name]))
                except KeyError:
                    # Unknown change type from an older log version — drop it.
                    self._conn.execute("DELETE FROM pending_events WHERE path = ?", (path,))
            self._conn.commit()
            return result
        except Exception as exc:
            logger.warning("[vault] Failed to read pending events: %s", type(exc).__name__)
            return []

    def set_fingerprint(self, path: str, fingerprint: str) -> None:
        """Persist the last-synced content fingerprint for ``path`` (#1302)."""
        if self._conn is None:
            return
        try:
            self._conn.execute(
                "INSERT OR REPLACE INTO fingerprints (path, fingerprint) VALUES (?, ?)",
                (path, fingerprint),
            )
            self._conn.commit()
        except Exception as exc:
            logger.warning("[vault] Failed to persist fingerprint for %s: %s", _log_name(path), type(exc).__name__)

    def remove_fingerprint(self, path: str) -> None:
        if self._conn is None:
            return
        try:
            self._conn.execute("DELETE FROM fingerprints WHERE path = ?", (path,))
            self._conn.commit()
        except Exception as exc:
            logger.warning("[vault] Failed to remove fingerprint for %s: %s", _log_name(path), type(exc).__name__)

    def fingerprints(self) -> dict[str, str]:
        """All persisted fingerprints, used to seed rename detection (#1302)."""
        if self._conn is None:
            return {}
        try:
            rows = self._conn.execute("SELECT path, fingerprint FROM fingerprints").fetchall()
            return dict(rows)
        except Exception as exc:
            logger.warning("[vault] Failed to read fingerprints: %s", type(exc).__name__)
            return {}

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:  # noqa: S110 — close must never raise; the log handle is being discarded anyway
                pass
            self._conn = None


# Event log bound by watch_vault() at startup so fingerprint writes also hit
# the persistent store. Unbound (unit tests, direct calls) → memory-only.
_event_log: PersistentEventLog | None = None


def _bind_event_log(event_log: PersistentEventLog) -> None:
    """Persist future fingerprints into ``event_log`` and seed the in-memory
    rename table with fingerprints saved before a crash/restart (#1302).

    Without this, a delete+add pair split by a restart is processed as
    delete+create and the note loses its id, XP and history.
    """
    global _event_log
    _event_log = event_log
    _fingerprints.update(event_log.fingerprints())


def _unbind_event_log() -> None:
    global _event_log
    _event_log = None


def _record_fingerprint(path: str, fingerprint: str) -> None:
    """Store a content fingerprint in memory AND in the bound event log."""
    _fingerprints[path] = fingerprint
    if _event_log is not None:
        _event_log.set_fingerprint(path, fingerprint)


def _drop_fingerprint(path: str) -> None:
    _fingerprints.pop(path, None)
    if _event_log is not None:
        _event_log.remove_fingerprint(path)


async def get_auth_token(client: httpx.AsyncClient, *, force: bool = False) -> str:
    """Return the INTERNAL_API_TOKEN service credential (#1275, #1302).

    Delegates to the lock-guarded single-flight refresher shared by every
    worker task, so a burst of concurrent 401s triggers exactly one fetch
    instead of a refresh stampede.
    """
    return await shared_auth.get_auth_token(client, force=force)


def _is_joidy_file(path: str) -> bool:
    return JOIDY_DIR in Path(path).parts


def _log_name(path: str | Path) -> str:
    """Log-safe display name for a vault path.

    Vault filenames may contain newlines or ANSI escape sequences that would
    forge log lines or inject terminal control sequences into ``docker logs``
    (#1301). ``repr()`` escapes every control character so a crafted name can
    never break out of a single line, and only the basename is shown so vault
    directory layout stays out of the logs (#1299).
    """
    return repr(Path(path).name)


# Paths already warned about for exceeding the size cap — one warning per
# path keeps a frequently-edited oversized file from spamming the log (#1298).
_oversized_warned: set[str] = set()


def _read_vault_file(path: Path) -> str | None:
    """Read a vault markdown file behind a ``stat().st_size`` gate (#1298).

    ``read_text()`` slurps the whole file, so a multi-GB ``.md`` would OOM the
    512M-limited worker and produce a giant JSON payload against the API.
    Files over ``settings.max_note_file_size`` are refused with a single
    warning; ``None`` (oversized or unreadable) tells callers to skip it.
    """
    if not _is_safe_vault_file(path, confined=False):
        return None
    try:
        size = path.stat().st_size
    except OSError:
        return None
    if size > settings.max_note_file_size:
        key = str(path)
        if key not in _oversized_warned:
            _oversized_warned.add(key)
            logger.warning(
                "[vault] Skipping oversized file %s (%d bytes > %d byte limit)",
                _log_name(path),
                size,
                settings.max_note_file_size,
            )
        return None
    return path.read_text(encoding="utf-8", errors="replace")


def _is_valid_vault_path(path: str, change_type: Change, vault_root: Path) -> bool:
    """Validate a vault event path before trusting it (#1294).

    Applied to live ``awatch`` events and to rows replayed from the
    persistent event log — that log sits on a host-mounted volume with no
    integrity check, so an injected row like ``("/app/.env", "added")``
    would otherwise be read and exfiltrated into a note on next startup.

    Checks: ``.md`` suffix, ``_joidy/`` exclusion, containment under
    ``vault_root`` after symlink resolution, and — for events that will read
    the file — non-symlink regular file. ``deleted`` events skip the
    existence checks: the file is already gone by definition.
    """
    if not path.endswith(".md"):
        return False
    if _is_joidy_file(path):
        return False
    try:
        root = vault_root.resolve()
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = root / candidate
        resolved = candidate.resolve()
        if not resolved.is_relative_to(root):
            return False
    except OSError:
        return False
    if change_type == Change.deleted:
        return True
    try:
        return not candidate.is_symlink() and candidate.is_file()
    except OSError:
        return False


def _vault_root() -> Path:
    """Resolved vault root used to confine file reads inside the vault."""
    return Path(settings.vault_path).resolve()


def _is_safe_vault_file(path: Path, *, confined: bool = True) -> bool:
    """Return True only for regular in-vault files (#1293).

    Rejects:
    - symlinks — a ``vault/leak.md -> /app/.env`` link would exfiltrate
      secrets (SECRET_KEY, POSTGRES_PASSWORD, GEMINI_API_KEY) into a note
      readable via the API;
    - paths whose resolved location escapes the vault root (e.g. a file
      reached through a symlinked parent directory) — only when
      ``confined`` is set;
    - non-regular files (FIFOs, sockets, devices).

    ``confined=False`` keeps the symlink/file-type checks while skipping
    the vault-root containment test; ``_read_vault_file`` uses that mode
    because the paths it receives are already confinement-validated
    upstream by ``_is_valid_vault_path``.
    """
    try:
        # is_symlink() uses lstat and must run BEFORE is_file(), which
        # follows links and would pass a symlink to a real file as "regular".
        if path.is_symlink():
            logger.warning("[vault] Skipping symlink: %s", _log_name(path))
            return False
        if not path.is_file():
            logger.warning("[vault] Skipping non-regular file: %s", _log_name(path))
            return False
        if confined:
            resolved = path.resolve()
            if not resolved.is_relative_to(_vault_root()):
                logger.warning(
                    "[vault] Skipping path outside vault: %s -> %s",
                    _log_name(path),
                    _log_name(resolved),
                )
                return False
    except Exception as exc:
        logger.warning("[vault] Skipping inaccessible path %s: %s", _log_name(path), exc)
        return False
    return True


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    """Extract YAML frontmatter and body from markdown."""
    frontmatter = {}
    body = content
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            fm_text = content[3:end].strip()
            body = content[end + 3 :].strip()
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
    return list({t.lower() for t in tags if t})


async def delete_note_by_path(path: str, client: httpx.AsyncClient, token: str) -> bool:
    """Delete the note matching ``source_path`` via the atomic by-path
    endpoint (#1302).

    The old flow listed notes, captured an id, then deleted it — a note
    re-created or updated between the list and the delete was removed
    anyway (TOCTOU). Now the API matches ``source_path`` and verifies the
    ``updated_at`` etag captured at lookup time inside a single locked
    transaction: a note that changed or was recreated in between answers
    409/404 and is left untouched (a later add/modify event resyncs it).

    Returns ``True`` when the delete is resolved (done, already absent, or
    refused by the API) and ``False`` when every attempt failed — the
    caller keeps the pending event so the delete is retried on the next
    startup instead of being silently dropped (#1534).
    """
    for attempt in range(3):
        try:
            current_token = await get_auth_token(client)
            cid = get_correlation_id()
            headers = {"X-Request-ID": cid}
            if current_token:
                headers["Authorization"] = f"Bearer {current_token}"
            r = await client.get(
                f"{settings.api_url}/notes/", params={"source_path": path}, headers=headers, timeout=10.0
            )
            if r.status_code == 401:
                logger.warning("[vault] Auth expired while deleting %s, refreshing token", _log_name(path))
                await get_auth_token(client, force=True)
                continue
            if r.status_code in (429, 500, 503):
                await asyncio.sleep(1 * (attempt + 1))
                continue
            if r.status_code == 404:
                return True  # already gone
            if r.status_code != 200:
                # 4xx/5xx raise below and retry via the except; odd statuses
                # (redirects, unexpected 2xx) are failures too — never report
                # a delete that did not happen (#1534).
                r.raise_for_status()
                logger.warning(
                    "[vault] Unexpected status %s looking up %s for delete",
                    r.status_code,
                    _log_name(path),
                )
                return False
            target = next((n for n in r.json() if n.get("source_path") == path), None)
            if target is None:
                return True  # nothing to delete
            del_res = await client.delete(
                f"{settings.api_url}/notes/by-path",
                params={
                    "source_path": path,
                    "expected_updated_at": target.get("updated_at") or "",
                },
                headers=headers,
                timeout=10.0,
            )
            if del_res.status_code == 401:
                await get_auth_token(client, force=True)
                continue
            if del_res.status_code == 409:
                logger.info(
                    "[vault] Skipping delete of %s — note changed since lookup",
                    _log_name(path),
                )
                return True
            if del_res.status_code == 404:
                return True  # already gone
            if del_res.status_code in (429, 500, 503):
                await asyncio.sleep(1 * (attempt + 1))
                continue
            del_res.raise_for_status()
            logger.info("[vault] Deleted: %s", _log_name(path))
            return True
        except Exception as e:
            if attempt == 2:
                # Exception type only — str(e) can embed request URLs carrying
                # source_path params; tracebacks leak the same (#1299, #1301).
                logger.error("[vault] Error deleting %s: %s", _log_name(path), type(e).__name__)
            await asyncio.sleep(1 * (attempt + 1))
    logger.error(
        "[vault] Delete retries exhausted for %s — event kept for next startup",
        _log_name(path),
    )
    return False


async def rename_note_path(old_path: str, new_path: Path, client: httpx.AsyncClient, token: str) -> bool:
    """Treat a delete+add pair as a rename: update the existing note's
    source_path instead of deleting and recreating it, preserving id/XP/history
    (#364).

    Returns ``True`` when the rename resolved and ``False`` on failure —
    the caller keeps both pending events for the next startup (#1534).
    """
    try:
        if not new_path.exists():
            return True
        content = _read_vault_file(new_path)
        if content is None:
            return True
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
                if r.status_code == 404:
                    break
                r.raise_for_status()
                break
            except Exception:
                if attempt == 2:
                    raise
                await asyncio.sleep(1)

        if not existing:
            # No note at the old path — fall back to a normal import of the new path.
            return await import_or_update_note(new_path, client, token)

        for attempt in range(5):
            current_token = await get_auth_token(client)
            cid = get_correlation_id()
            headers = {"X-Request-ID": cid, "X-From-Vault": "1"}
            if current_token:
                headers["Authorization"] = f"Bearer {current_token}"
            res = await client.put(
                f"{settings.api_url}/notes/{existing['id']}",
                json={
                    "title": title,
                    "content": content,
                    "tags": tags,
                    "source": "obsidian",
                    "source_path": str(new_path),
                },
                headers=headers,
                timeout=10.0,
            )
            if res.status_code == 401:
                await get_auth_token(client, force=True)
                continue
            if res.status_code in (429, 500, 503):
                await asyncio.sleep(2**attempt)
                continue
            res.raise_for_status()
            _record_fingerprint(str(new_path), _fingerprint(content))
            _drop_fingerprint(old_path)
            logger.info("[vault] Renamed: %s -> %s", _log_name(old_path), _log_name(new_path))
            return True
        logger.error(
            "[vault] Rename retries exhausted for %s -> %s — events kept for next startup",
            _log_name(old_path),
            _log_name(new_path),
        )
        return False
    except Exception as e:
        # Exception type only — str(e) can embed request URLs carrying
        # source_path params; tracebacks leak the same (#1299, #1301).
        logger.error(
            "[vault] Error renaming %s -> %s: %s",
            _log_name(old_path),
            _log_name(new_path),
            type(e).__name__,
        )
        return False


async def import_or_update_note(
    filepath: Path, client: httpx.AsyncClient, token: str, *, bulk_import: bool = False
) -> bool:
    """Sync one vault file to the API.

    Returns ``True`` when the note was synced (or there was nothing to do)
    and ``False`` when the sync failed — the caller keeps the pending event
    so it is retried on the next startup instead of being dropped (#1534).
    """
    try:
        if not filepath.exists():
            return True
        content = _read_vault_file(filepath)
        if content is None:
            return True
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
                    logger.warning("[vault] Auth expired while checking %s, refreshing token", _log_name(filepath))
                    await get_auth_token(client, force=True)
                    continue
                if r.status_code == 200:
                    notes = r.json()
                    for n in notes:
                        if n.get("source_path") == str(filepath):
                            existing = n
                            break
                    break
                if r.status_code == 404:
                    break
                # 4xx/5xx raise here and retry via the except below — a failed
                # lookup must not be mistaken for "note does not exist" and
                # trigger a duplicate create (#1534).
                r.raise_for_status()
                break
            except Exception:
                if attempt == 2:
                    raise
                await asyncio.sleep(1)

        payload = {"title": title, "content": content, "tags": tags, "source": "obsidian", "source_path": str(filepath)}

        synced = False
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
                    json={
                        "title": title,
                        "content": content,
                        "tags": tags,
                        "source": "obsidian",
                        "source_path": str(filepath),
                    },
                    headers=headers,
                    timeout=10.0,
                )
            else:
                res = await client.post(f"{settings.api_url}/notes/", json=payload, headers=headers, timeout=10.0)

            if res.status_code == 401:
                logger.warning("[vault] Auth expired while syncing %s, refreshing token", _log_name(filepath))
                await get_auth_token(client, force=True)
                continue

            if res.status_code in (429, 500, 503):
                wait = 2**attempt
                logger.warning(
                    "[vault] %s syncing %s (attempt %d/%d), retrying in %ss",
                    res.status_code,
                    _log_name(filepath),
                    attempt + 1,
                    5,
                    wait,
                )
                await asyncio.sleep(wait)
                continue

            res.raise_for_status()
            synced = True
            break

        if not synced:
            # Every attempt hit a retryable status or auth failure — do NOT
            # fingerprint/log as synced; report failure so the caller keeps
            # the event for the next startup (#1534).
            logger.error(
                "[vault] Sync retries exhausted for %s — event kept for next startup",
                _log_name(filepath),
            )
            return False

        _record_fingerprint(str(filepath), _fingerprint(content))
        logger.info("[vault] Synced: %s", _log_name(filepath))
        return True

    except Exception as e:
        # Exception type only — str(e) can embed request URLs carrying
        # source_path params; tracebacks leak the same (#1299, #1301).
        logger.error("[vault] Error syncing %s: %s", _log_name(filepath), type(e).__name__)
        return False


async def initial_scan(vault_path: Path, client: httpx.AsyncClient, token: str):
    """On startup, import all .md files not in _joidy/."""
    # Same validation as live events: skips dirs named *.md and symlinks
    # (Obsidian does not index them either) and anything resolving outside
    # the vault root (#1294).
    md_files = [p for p in vault_path.rglob("*.md") if _is_valid_vault_path(str(p), Change.modified, vault_path)]

    # Unchanged-file short-circuit (#1535): _record_fingerprint only writes a
    # path's content hash AFTER a successful sync (#1534) and _bind_event_log
    # seeds _fingerprints from the persistent event log, so a match proves the
    # API already holds exactly this content — a healthy (re)start becomes a
    # no-op instead of a GET + full-content PUT per note. Two safety valves:
    # - a path with a pending event is never skipped (its last sync may have
    #   failed and the replay before this scan may have failed too, #1534);
    # - a successful delete drops the fingerprint (see _process_batch), so a
    #   file recreated with identical content still resyncs.
    pending_paths = {path for path, _ in _event_log.pending()} if _event_log is not None else set()
    to_sync: list[Path] = []
    skipped = 0
    for filepath in md_files:
        stored = _fingerprints.get(str(filepath))
        if stored is not None and str(filepath) not in pending_paths:
            content = _read_vault_file(filepath)
            if content is not None and _fingerprint(content) == stored:
                skipped += 1
                continue
        to_sync.append(filepath)
    logger.info(
        "[vault] Initial scan: %d markdown files found, %d unchanged skipped",
        len(md_files),
        skipped,
    )

    semaphore = asyncio.Semaphore(4)

    async def process_file(filepath: Path):
        async with semaphore:
            await import_or_update_note(filepath, client, token, bulk_import=True)

    await asyncio.gather(*(process_file(filepath) for filepath in to_sync), return_exceptions=True)

    for _attempt in range(2):
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


async def _process_batch(
    pending: dict[str, Change],
    client: httpx.AsyncClient,
    token: str,
    event_log: PersistentEventLog,
    in_flight: set[asyncio.Task] | None = None,
):
    """Process one deduped batch of vault events.

    Shared by the live consumer and by startup replay (#1302): events
    persisted before a crash are reconciled through this same path BEFORE
    the initial scan, so a delete+add pair spanning a restart is still
    detected as a rename — the note keeps its id/XP/history instead of
    being deleted and re-created as a duplicate at the new path.
    """
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
                if Path(new_path).exists() and _is_valid_vault_path(new_path, Change.added, _vault_root()):
                    content = _read_vault_file(Path(new_path))
                    if content is not None and _fingerprint(content) == old_fp:
                        renames.append((old_path, new_path))
                        consumed_adds.add(new_path)
                        break
            except Exception:  # noqa: S112 — unreadable candidate file; try the next one
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
        # Re-validate queued paths: the awatch producer filters events
        # before enqueue, but persisted replays and direct queue
        # injection must not reach a vault read unvalidated (#1293).
        if not _is_valid_vault_path(path, change_type, _vault_root()):
            logger.warning("[vault] Skipping invalid queued path %s", _log_name(path))
            event_log.remove(path)
            return
        lock = await _get_file_lock(path)
        async with lock:
            try:
                if change_type == Change.deleted and Path(path).exists():
                    # The file reappeared after the delete event fired —
                    # recreated inside the debounce window or while the
                    # worker was down. Resync instead of deleting so the
                    # note keeps its id/history (#1302).
                    change_type = Change.modified
                # Shield the critical write so a shutdown cancellation
                # does not interrupt a mid-flight API call (#371).
                if change_type == Change.deleted:
                    ok = await asyncio.shield(delete_note_by_path(path, client, token))
                else:
                    ok = await asyncio.shield(import_or_update_note(Path(path), client, token))
                if ok:
                    event_log.remove(path)
                    if change_type == Change.deleted:
                        # The note is gone from the API — the stored content
                        # fingerprint no longer describes synced state, and
                        # keeping it would let initial_scan skip a file that
                        # was recreated with identical content (#1535). Safe
                        # for rename detection: delete+add pairs are matched
                        # before deletes are processed (see _process_batch).
                        _drop_fingerprint(path)
                else:
                    # Sync failed after retries — keep the event so it is
                    # retried on the next startup instead of dropped (#1534).
                    logger.warning(
                        "[vault] %s %s failed — event kept for next startup",
                        change_type.name,
                        _log_name(path),
                    )
            except asyncio.CancelledError:
                # Propagate cancellation but keep the event logged so
                # it is retried on the next startup.
                raise
            except Exception as exc:
                # Exception type only — tracebacks/str(exc) can embed
                # vault paths and request URLs (#1299, #1301).
                logger.error(
                    "[vault] Failed to process %s (%s): %s",
                    _log_name(path),
                    change_type.name,
                    type(exc).__name__,
                )

    async def process_rename(old_path: str, new_path: str):
        if not _is_valid_vault_path(new_path, Change.added, _vault_root()):
            logger.warning("[vault] Skipping invalid rename target %s", _log_name(new_path))
            event_log.remove(old_path)
            event_log.remove(new_path)
            return
        lock = await _get_file_lock(old_path)
        async with lock:
            try:
                ok = await asyncio.shield(rename_note_path(old_path, Path(new_path), client, token))
                if ok:
                    event_log.remove(old_path)
                    event_log.remove(new_path)
                else:
                    # Rename failed after retries — keep both events so the
                    # pair is retried on the next startup (#1534).
                    logger.warning(
                        "[vault] Rename %s -> %s failed — events kept for next startup",
                        _log_name(old_path),
                        _log_name(new_path),
                    )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error(
                    "[vault] Failed to rename %s -> %s: %s",
                    _log_name(old_path),
                    _log_name(new_path),
                    type(exc).__name__,
                )

    batch_tasks: list[asyncio.Task] = []
    for old_path, new_path in renames:
        batch_tasks.append(asyncio.ensure_future(process_rename(old_path, new_path)))
    for path, change_type in remaining.items():
        batch_tasks.append(asyncio.ensure_future(process(path, change_type)))

    if in_flight is not None:
        in_flight.update(batch_tasks)
    await asyncio.gather(*batch_tasks, return_exceptions=True)
    if in_flight is not None:
        in_flight.difference_update(batch_tasks)


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
            await _process_batch(pending, client, token, event_log, _in_flight)
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


def _replay_pending_events(
    event_log: PersistentEventLog,
    vault_root: Path,
) -> dict[str, Change]:
    """Collect events persisted before a crash, after re-validation (#1294).

    The event log lives on a host-mounted volume with no integrity check, so
    replayed rows get the same validation as live ``awatch`` events. Rows that
    fail are refused, logged once, and dropped from the log so they are not
    re-validated on every startup. Returns the accepted events keyed by path
    (last write wins, mirroring the in-memory batch dedup and the log's own
    primary key).
    """
    accepted: dict[str, Change] = {}
    for path, change_type in event_log.pending():
        if not _is_valid_vault_path(path, change_type, vault_root):
            logger.warning(
                "[vault] Refusing invalid persisted event %s (%s) — dropping",
                _log_name(path),
                change_type.name,
            )
            event_log.remove(path)
            continue
        accepted[path] = change_type
    return accepted


async def watch_vault():
    set_correlation_id(f"worker-{uuid.uuid4().hex[:12]}")
    vault_path = Path(settings.vault_path)
    if not vault_path.exists():
        logger.warning("[vault] Vault path %s does not exist - skipping file watch", vault_path)
        return

    logger.info("[vault] Watching: %s", vault_path)

    event_log = PersistentEventLog(settings.event_log_path)
    # Persist fingerprints into the log and seed the in-memory rename table
    # with the fingerprints saved before the last shutdown (#1302).
    _bind_event_log(event_log)
    async with httpx.AsyncClient(timeout=30.0) as client:
        consumer = None
        try:
            token = await get_auth_token(client)
            if not token and settings.app_env == "production":
                logger.error("[vault] INTERNAL_API_TOKEN is not configured; aborting vault sync")
                return

            # Replay events persisted but not processed before a previous
            # crash (#371) BEFORE the initial scan (#1302): a delete+add
            # pair spanning the restart is reconciled as a rename through
            # the same code path as live batches, so the note keeps its
            # id/XP/history and the scan cannot create a duplicate at the
            # new path. Replayed rows get the same validation as live
            # events — the log is host-writable with no integrity check,
            # so injected paths would otherwise be synced on startup
            # (#1294). Successfully processed events are removed from the
            # log by _process_batch; anything left stays pending for the
            # next startup.
            replayed = _replay_pending_events(event_log, vault_path)
            if replayed:
                logger.info("[vault] Recovering %d pending event(s) from previous run", len(replayed))
                await _process_batch(replayed, client, token, event_log)

            await initial_scan(vault_path, client, token)

            queue: asyncio.Queue[VaultEvent] = asyncio.Queue(maxsize=1000)

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
                            if not _is_valid_vault_path(path, change_type, vault_path):
                                continue
                            event_log.add(path, change_type)
                            await queue.put(VaultEvent(path=path, change_type=change_type))
                    break
                except Exception as e:
                    if shutdown_event.is_set():
                        break
                    logger.error(
                        "[vault] Watcher error (attempt %d/%d): %s", attempt + 1, max_retries, type(e).__name__
                    )
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
                    except (asyncio.CancelledError, Exception):  # noqa: S110 — shutdown path: swallow the expected cancellation
                        pass
        finally:
            _unbind_event_log()
            event_log.close()
            logger.info("[vault] Watcher stopped cleanly")
