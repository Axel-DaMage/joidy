import os
import re
import shutil

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from services.auth_service import get_current_user
from services.vault_paths import (
    JOIDY_VAULT_DIR,
    get_effective_vault_path,
    resolve_confined_source_path,
)

router = APIRouter(prefix="/folders", tags=["folders"])

# Characters forbidden in Obsidian folder names (mirrors note sanitization).
_INVALID_NAME_CHARS = re.compile(r'[\\/:*?"<>|]')


class FolderCreate(BaseModel):
    path: str


def _is_hidden_or_internal(name: str) -> bool:
    """True for path segments the folder API must never list nor mutate.

    Single source of truth shared by _list_vault_folders (traversal pruning)
    and _get_safe_path (create/delete denylist, #1313): any hidden directory
    (".obsidian", ".git", ".trash", …) plus the internal "_joidy/" state dir,
    at any depth. ``JOIDY_VAULT_DIR`` is the canonical name from
    ``services.vault_paths``.
    """
    return name.startswith(".") or name == JOIDY_VAULT_DIR


def _get_safe_path(vault: str, requested: str) -> str:
    """Resolve a vault-relative path and make sure it stays inside the vault.

    Confinement is delegated to ``resolve_confined_source_path`` — the same
    canonical realpath+commonpath boundary the notes router uses (#1287) —
    so the vault root can never resolve two different ways (#1532). On
    rejection the reason is mapped back onto the #1313 API contract:
    - the vault root itself: "." or traversal ("a/..", "%2e%2e" segments
      decoded by the router) resolve to ``vault`` — and DELETE would rmtree
      the whole vault;
    - any hidden/internal segment, mirroring _list_vault_folders pruning, so
      directories the API hides (".obsidian", ".git", ".trash", "_joidy", …)
      cannot be created or deleted either;
    - anything else (traversal, prefix confusion, symlink escape).
    """
    resolved = resolve_confined_source_path(os.path.join(vault, requested), require_markdown=False)
    if resolved is not None:
        return resolved
    if os.path.realpath(os.path.join(vault, requested)) == os.path.realpath(vault):
        raise HTTPException(status_code=400, detail="Cannot target the vault root")
    if any(_is_hidden_or_internal(part) for part in requested.split("/")):
        raise HTTPException(status_code=400, detail="Folder is hidden or internal")
    raise HTTPException(status_code=400, detail="Invalid path")


def _validate_folder_name(path: str) -> None:
    """Basic validation for a vault-relative folder path."""
    for part in path.split("/"):
        if not part or part in (".", ".."):
            raise HTTPException(status_code=400, detail="Invalid folder name")
        if _INVALID_NAME_CHARS.search(part):
            raise HTTPException(status_code=400, detail="Invalid folder name")
        if len(part) > 255:
            raise HTTPException(status_code=400, detail="Folder name too long")


def _list_vault_folders(vault: str) -> list[str]:
    """Recursively list vault directories as vault-relative posix paths.

    Prunes hidden dirs (".obsidian", ".git", …) and the internal "_joidy/"
    directory from traversal so they never reach the tree.
    """
    base = os.path.realpath(vault)
    folders: list[str] = []
    for root, dirs, _files in os.walk(base):
        dirs[:] = [d for d in dirs if not _is_hidden_or_internal(d)]
        rel = os.path.relpath(root, base)
        for d in dirs:
            rel_dir = d if rel == "." else os.path.join(rel, d)
            folders.append(rel_dir.replace(os.sep, "/"))
    folders.sort()
    return folders


@router.get("/")
def list_folders(user: dict = Depends(get_current_user)):
    vault = get_effective_vault_path()
    if not vault:
        raise HTTPException(status_code=400, detail="OBSIDIAN_VAULT_PATH not set")

    try:
        folders = _list_vault_folders(vault)
        return {"folders": folders}
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to list folders")


@router.post("/")
def create_folder(
    folder: FolderCreate,
    user: dict = Depends(get_current_user),
):
    vault = get_effective_vault_path()
    if not vault:
        raise HTTPException(status_code=400, detail="OBSIDIAN_VAULT_PATH not set")

    _validate_folder_name(folder.path)
    full_path = _get_safe_path(vault, folder.path)
    if os.path.exists(full_path):
        raise HTTPException(status_code=400, detail="Folder already exists")

    try:
        os.makedirs(full_path, exist_ok=True)
        return {"status": "ok", "path": folder.path}
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to create folder")


@router.delete("/{path:path}")
def delete_folder(
    path: str,
    user: dict = Depends(get_current_user),
):
    vault = get_effective_vault_path()
    if not vault:
        raise HTTPException(status_code=400, detail="OBSIDIAN_VAULT_PATH not set")

    # Same contract as create (#1313): reject "."/".."/empty segments and
    # invalid characters before the resolved path ever reaches rmtree.
    _validate_folder_name(path)
    full_path = _get_safe_path(vault, path)
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="Folder not found")

    if not os.path.isdir(full_path):
        raise HTTPException(status_code=400, detail="Not a folder")

    try:
        shutil.rmtree(full_path)
        return {"status": "ok"}
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to delete folder")
