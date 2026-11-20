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

This module is also the single confinement boundary for every filesystem
access driven by a note's ``source_path`` (#1287, #1314):
``resolve_confined_source_path`` decides whether a stored path may be read
from or written to, and the notes router uses the same function to reject
unsafe client-supplied paths with a generic ``400``.
"""

import os
import posixpath
import re

from config import settings
from services.env_file import read_env

# A Windows-style absolute path (``C:/vault/x.md``) must never be treated as
# vault-relative — anchoring it under the vault would silently fabricate a
# ``/vault/C:/...`` target.
_DRIVE_ABSOLUTE = re.compile(r"^[A-Za-z]:/")

# Joidy-managed subtree inside the vault. Notes must never read or write it —
# it holds Joidy-owned state files, not user notes (mirrors the worker-side
# ``_is_joidy_file`` filter and the folders router's pruning).
JOIDY_VAULT_DIR = "_joidy"


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
    rel = path[len(prefix) :]
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
    the effective domain are returned as-is. Vault-relative paths
    (``Daily/note.md`` — what the file-tree move UI and some webhook clients
    send) are anchored under the effective root. Unknown absolute roots pass
    through unchanged, including traversals under a known root (``..`` is
    never re-anchored inside the vault — confinement refuses any path that
    resolves outside the effective root).
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
    if not clean.startswith("/") and not _DRIVE_ABSOLUTE.match(clean):
        # Relative path: interpret it as vault-relative and collapse any
        # interior ``.``/``..`` segments onto the canonical domain. Escapes
        # land outside the vault root and are refused downstream by
        # resolve_confined_source_path.
        return posixpath.normpath(f"{effective}/{clean}")
    return clean


def resolve_confined_source_path(
    path: str | None,
    *,
    require_markdown: bool = True,
) -> str | None:
    """Resolve ``path`` to a real filesystem path strictly inside the vault.

    Returns the canonical (symlink-resolved) absolute path when it is safe to
    use, or ``None`` when the path must not be touched:

    - no vault is configured, or ``path`` is empty;
    - the realpath escapes the effective vault root — prefix confusion
      (``/vault_evil/x`` for vault ``/vault``), traversal, or a symlink
      planted inside the vault pointing outside (#1287);
    - the path is the vault root itself rather than a file inside it;
    - a path component is hidden (leading ``.`` — covers ``.obsidian``,
      ``.git``, dot-files) or is ``_joidy`` (#1314);
    - ``require_markdown`` is set and the filename does not end in ``.md``.

    Both the vault root and the candidate are compared via
    ``os.path.realpath`` + ``os.path.commonpath`` — never a raw
    ``startswith`` prefix check.
    """
    effective = get_effective_vault_path()
    if not effective or not path or not str(path).strip():
        return None
    try:
        vault_real = os.path.realpath(effective)
        resolved = os.path.realpath(_clean_separators(str(path).strip()))
        if os.path.commonpath((vault_real, resolved)) != vault_real:
            return None
        rel = os.path.relpath(resolved, vault_real)
    except (OSError, ValueError):
        return None
    parts = [p for p in rel.split(os.sep) if p not in ("", ".")]
    if not parts:
        return None
    if any(p == ".." or p == JOIDY_VAULT_DIR or p.startswith(".") for p in parts):
        return None
    if require_markdown and not resolved.lower().endswith(".md"):
        return None
    return resolved
