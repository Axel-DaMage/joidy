"""Canonical ``source_path`` domain for notes (issue #1099).

The frontend builds note source paths from the vault path it sees on
``GET /config`` — the *host* vault path stored in ``.env`` (e.g.
``/home/user/ObsidianVault``). Inside the containers the same vault is
mounted at ``/vault`` and ``OBSIDIAN_VAULT_PATH`` is overridden to ``/vault``.

Historically those two domains coexisted in ``notes.source_path``: notes
created from the UI kept host paths (so ``write_to_vault`` silently skipped
them and ``GET /notes?source_path=/vault/...`` from the watcher never
matched), while vault watcher imports stored ``/vault`` paths. The frontend
note tree (``lib/utils/fileTree.ts``) already assumes the ``/vault`` domain
(it strips a leading ``/vault/`` to group folders).

Everything in here is best-effort: if a path does not live under any known
vault root, it is returned unchanged so exotic inputs cannot block creation.
"""

import os
import re

from config import settings
from services.env_file import read_env


def _clean_separators(path: str) -> str:
    """Normalize backslashes so Windows-style host paths can match."""
    return path.replace("\\", "/")


def _strip_root(path: str, root: str) -> str | None:
    """Return ``path`` relative to ``root`` (edge-safe), or ``None``."""
    root = _clean_separators(root).rstrip("/")
    path = _clean_separators(path)
    if path == root:
        return ""
    prefix = root + "/"
    if not path.startswith(prefix):
        return None
    rel = path[len(prefix):]
    # Reject traversal — the service layer must never tolerate a source path
    # that escapes the vault (write_to_vault would happily follow it).
    if any(part == ".." for part in rel.split("/")):
        return None
    return rel


def get_effective_vault_path() -> str:
    """The vault path valid *inside* this process (the API container)."""
    return _clean_separators(settings.obsidian_vault_path or "")


def _vault_roots() -> list[str]:
    """Candidate roots a client-side path may use for the same vault.

    The container value first (already canonical), then the host-side path
    from the persisted ``.env`` — the domain the settings UI and frontend
    operate in.
    """
    roots: list[str] = []
    effective = get_effective_vault_path()
    if effective:
        roots.append(effective)
    try:
        persisted = _clean_separators(read_env().get("OBSIDIAN_VAULT_PATH", ""))
    except Exception:
        persisted = ""
    if persisted and persisted not in roots:
        roots.append(persisted)
    return roots


def normalize_source_path(path: str | None) -> str | None:
    """Rewrite a note source path onto the effective (container) vault domain.

    ``/home/user/Vault/Daily/2025-01-01.md`` with ``OBSIDIAN_VAULT_PATH=/vault``
    in the container becomes ``/vault/Daily/2025-01-01.md``. Paths already in
    the effective domain are returned as-is; unknown roots pass through
    unchanged, including traversals under a known root (``..`` is never
    re-anchored inside the vault — ``write_to_vault``'s prefix guard refuses
    any path outside the effective root).
    """
    if not path or not path.strip():
        return None
    clean = _clean_separators(path.strip())
    effective = get_effective_vault_path()
    if not effective:
        return clean
    for root in _vault_roots():
        rel = _strip_root(clean, root)
        if rel is None:
            continue
        return f"{effective}/{rel}" if rel else effective
    return clean
