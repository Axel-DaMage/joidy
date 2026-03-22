"""
Obsidian Vault Watcher

Monitors the vault directory for .md file changes (excluding _joidy/).
On change: imports the note via the API → triggers AI classification.

Uses debouncing: waits 2s after the last change to a file before processing,
to avoid reading files while Obsidian is still writing them.
"""

import asyncio
import re
from datetime import datetime
from pathlib import Path

import httpx
from watchfiles import awatch, Change

from config import settings

JOIDY_DIR = "_joidy"
DEBOUNCE_SECONDS = 2.0


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


async def import_or_update_note(filepath: Path, client: httpx.AsyncClient):
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
        frontmatter, body = _parse_frontmatter(content)
        title = frontmatter.get("title") or filepath.stem.replace("-", " ").replace("_", " ").title()
        tags = _extract_tags_from_content(content, frontmatter)

        # Check if note already exists by source_path
        r = await client.get(
            f"{settings.api_url}/notes/",
            params={"source_path": str(filepath)},
            timeout=10.0,
        )
        existing = None
        if r.status_code == 200:
            notes = r.json()
            for n in notes:
                if n.get("source_path") == str(filepath):
                    existing = n
                    break

        payload = {"title": title, "content": content, "tags": tags, "source": "obsidian", "source_path": str(filepath)}

        if existing:
            await client.put(f"{settings.api_url}/notes/{existing['id']}", json={"title": title, "content": content, "tags": tags, "source": "obsidian", "source_path": str(filepath)}, timeout=10.0)
        else:
            await client.post(f"{settings.api_url}/notes/", json=payload, timeout=10.0)

        print(f"[vault] Synced: {filepath.name}")

    except Exception as e:
        print(f"[vault] Error syncing {filepath}: {e}")


async def initial_scan(vault_path: Path, client: httpx.AsyncClient):
    """On startup, import all .md files not in _joidy/."""
    md_files = [p for p in vault_path.rglob("*.md") if not _is_joidy_file(str(p))]
    print(f"[vault] Initial scan: {len(md_files)} markdown files found")
    for filepath in md_files:
        await import_or_update_note(filepath, client)
        await asyncio.sleep(0.1)  # Don't hammer the API


async def watch_vault():
    vault_path = Path(settings.vault_path)
    if not vault_path.exists():
        print(f"[vault] Vault path {vault_path} does not exist — skipping file watch")
        return

    print(f"[vault] Watching: {vault_path}")

    # Pending debounce: path → asyncio.Task
    pending: dict[str, asyncio.Task] = {}

    async with httpx.AsyncClient() as client:
        # Initial scan on startup
        await initial_scan(vault_path, client)

        async for changes in awatch(str(vault_path)):
            for change_type, path in changes:
                if not path.endswith(".md"):
                    continue
                if _is_joidy_file(path):
                    continue  # Never import _joidy/ files
                if change_type == Change.deleted:
                    continue

                # Debounce: cancel existing task for this file, create new one
                if path in pending:
                    pending[path].cancel()

                async def process(p=path):
                    await asyncio.sleep(DEBOUNCE_SECONDS)
                    await import_or_update_note(Path(p), client)
                    pending.pop(p, None)

                pending[path] = asyncio.create_task(process())
