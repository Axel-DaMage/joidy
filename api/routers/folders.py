import os
import re
import shutil

from config import settings
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from services.auth_service import get_current_user

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
    at any depth.
    """
    return name.startswith(".") or name == "_joidy"


def _get_safe_path(vault: str, requested: str) -> str:
    """Resolve a vault-relative path and make sure it stays inside the vault.

    Beyond containment (commonpath), targets that must never be mutated
    through this API are rejected (#1313):
    - the vault root itself: "." or traversal ("a/..", "%2e%2e" segments
      decoded by the router) resolve to ``vault``, which the commonpath check
      alone accepts — and DELETE would rmtree the whole vault;
    - any hidden/internal segment, mirroring _list_vault_folders pruning, so
      directories the API hides (".obsidian", ".git", ".trash", "_joidy", …)
      cannot be created or deleted either.
    """
    full_path = os.path.realpath(os.path.join(vault, requested))
    vault_path = os.path.realpath(vault)
    if os.path.commonpath([full_path, vault_path]) != vault_path:
        raise HTTPException(status_code=400, detail="Invalid path")
    if full_path == vault_path:
        raise HTTPException(status_code=400, detail="Cannot target the vault root")
    if any(_is_hidden_or_internal(part) for part in requested.split("/")):
        raise HTTPException(status_code=400, detail="Folder is hidden or internal")
    return full_path


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
    vault = settings.obsidian_vault_path
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
    vault = settings.obsidian_vault_path
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
    vault = settings.obsidian_vault_path
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
