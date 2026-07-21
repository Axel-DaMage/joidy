"""
Obsidian Vault Watcher

Monitors the vault directory for .md file changes (excluding _joidy/).
On change: imports the note via the API → triggers AI classification.

Uses debouncing: waits 2s after the last change to a file before processing,
to avoid reading files while Obsidian is still writing them.
"""

import asyncio
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import httpx
from config import settings
from watchfiles import Change, awatch

logger = logging.getLogger(__name__)

JOIDY_DIR = "_joidy"
DEBOUNCE_SECONDS = 2.0
QUEUE_FLUSH_INTERVAL = 0.5


@dataclass(frozen=True)
class VaultEvent:
    path: str
    change_type: Change


async def get_auth_token(client: httpx.AsyncClient) -> str:
    if not settings.auth_password:
        return ""
    try:
        r = await client.post(f"{settings.api_url}/auth/login", params={"password": settings.auth_password})
        if r.status_code == 200:
            return r.json().get("access_token", "")
    except Exception as e:
        logger.error("[vault] Failed to get auth token: %s", e)
    return ""

auth_token = ""

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
            r = await client.get(f"{settings.api_url}/notes/", params={"source_path": path}, headers={"Authorization": f"Bearer {token}"} if token else None)
            if r.status_code == 200:
                notes = r.json()
                for n in notes:
                    if n.get("source_path") == path:
                        await client.delete(f"{settings.api_url}/notes/{n['id']}", headers={"Authorization": f"Bearer {token}"} if token else None)
                        logger.info("[vault] Deleted: %s", Path(path).name)
                        return
            break # Success or not found
        except Exception as e:
            if attempt == 2:
                logger.exception("[vault] Error deleting %s: %s", path, e)
            await asyncio.sleep(1 * (attempt + 1))


async def import_or_update_note(filepath: Path, client: httpx.AsyncClient, token: str, *, bulk_import: bool = False):
    try:
        if not filepath.exists():
            return
        content = filepath.read_text(encoding="utf-8", errors="replace")
        frontmatter, body = _parse_frontmatter(content)
        title = frontmatter.get("title") or filepath.stem.replace("-", " ").replace("_", " ").title()
        tags = _extract_tags_from_content(content, frontmatter)

        # Check if note already exists by source_path (with retry)
        existing = None
        for attempt in range(3):
            try:
                r = await client.get(
                    f"{settings.api_url}/notes/",
                    params={"source_path": str(filepath)},
                    headers={"Authorization": f"Bearer {token}"} if token else None,
                    timeout=10.0,
                )
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
        headers = {"X-Bulk-Import": "1"} if bulk_import else {}
        if token: headers["Authorization"] = f"Bearer {token}"

        if existing:
            res = await client.put(
                f"{settings.api_url}/notes/{existing['id']}",
                json={"title": title, "content": content, "tags": tags, "source": "obsidian", "source_path": str(filepath)},
                headers=headers,
                timeout=10.0,
            )
        else:
            res = await client.post(f"{settings.api_url}/notes/", json=payload, headers=headers, timeout=10.0); res.raise_for_status()

        logger.info("[vault] Synced: %s", filepath.name)

    except Exception as e:
        logger.exception("[vault] Error syncing %s: %s", filepath, e)


async def initial_scan(vault_path: Path, client: httpx.AsyncClient, token: str):
    """On startup, import all .md files not in _joidy/."""
    md_files = [p for p in vault_path.rglob("*.md") if not _is_joidy_file(str(p))]
    logger.info("[vault] Initial scan: %s markdown files found", len(md_files))

    semaphore = asyncio.Semaphore(8)

    async def process_file(filepath: Path):
        async with semaphore:
            await import_or_update_note(filepath, client, token, bulk_import=True)

    await asyncio.gather(*(process_file(filepath) for filepath in md_files), return_exceptions=True)
    await client.post(f"{settings.api_url}/notes/rebuild-derived", headers={"Authorization": f"Bearer {token}"} if token else None, timeout=30.0)


async def _consume_vault_events(
    queue: asyncio.Queue[VaultEvent],
    client: httpx.AsyncClient,
    token: str,
):
    while True:
        try:
            first_event = await queue.get()
            pending: dict[str, Change] = {first_event.path: first_event.change_type}

            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=QUEUE_FLUSH_INTERVAL)
                    pending[event.path] = event.change_type
                except TimeoutError:
                    break

            await asyncio.sleep(DEBOUNCE_SECONDS)

            async def process(path: str, change_type: Change):
                try:
                    if change_type == Change.deleted:
                        await delete_note_by_path(path, client, token)
                    else:
                        await import_or_update_note(Path(path), client, token)
                except Exception:
                    logger.exception("[vault] Failed to process %s (%s)", path, change_type)

            await asyncio.gather(*(process(path, change_type) for path, change_type in pending.items()), return_exceptions=True)
        except TimeoutError:
            continue
        except asyncio.CancelledError:
            # Drain remaining queue items before exiting
            drained = 0
            while not queue.empty():
                try:
                    queue.get_nowait()
                    drained += 1
                except asyncio.QueueEmpty:
                    break
            if drained:
                logger.info("[vault] Drained %d orphaned events on shutdown", drained)
            return
        except Exception:
            logger.exception("[vault] Unexpected error in event consumer")
            await asyncio.sleep(1)  # Prevent tight error loop


async def watch_vault():
    vault_path = Path(settings.vault_path)
    if not vault_path.exists():
        logger.warning("[vault] Vault path %s does not exist - skipping file watch", vault_path)
        return

    logger.info("[vault] Watching: %s", vault_path)

    async with httpx.AsyncClient() as client:
        consumer = None
        try:
            token = await get_auth_token(client)
            await initial_scan(vault_path, client, token)

            queue: asyncio.Queue[VaultEvent] = asyncio.Queue(maxsize=1000)
            consumer = asyncio.create_task(_consume_vault_events(queue, client, token), name="vault_event_consumer")

            max_retries = 5
            retry_delay = 1.0
            for attempt in range(max_retries):
                try:
                    async for changes in awatch(str(vault_path)):
                        retry_delay = 1.0
                        for change_type, path in changes:
                            if not path.endswith(".md"):
                                continue
                            if _is_joidy_file(path):
                                continue
                            await queue.put(VaultEvent(path=path, change_type=change_type))
                    break
                except Exception as e:
                    logger.error("[vault] Watcher error (attempt %d/%d): %s", attempt + 1, max_retries, e)
                    if attempt == max_retries - 1:
                        raise
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, 60.0)
        finally:
            if consumer is not None:
                consumer.cancel()
                try:
                    await asyncio.wait_for(consumer, timeout=5.0)
                except (TimeoutError, asyncio.CancelledError):
                    pass
            logger.info("[vault] Watcher stopped cleanly")
