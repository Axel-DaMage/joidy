import os
import shutil
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from services.auth_service import get_current_user

router = APIRouter(prefix="/folders", tags=["folders"])


class FolderCreate(BaseModel):
    path: str


def _get_safe_path(vault: str, requested: str) -> str:
    """Resolve a vault-relative path and make sure it stays inside the vault."""
    full_path = os.path.realpath(os.path.join(vault, requested))
    vault_path = os.path.realpath(vault)
    if os.path.commonpath([full_path, vault_path]) != vault_path:
        raise HTTPException(status_code=400, detail="Invalid path")
    return full_path


@router.post("/")
def create_folder(
    folder: FolderCreate,
    user: dict = Depends(get_current_user),
):
    vault = os.environ.get("OBSIDIAN_VAULT_PATH")
    if not vault:
        raise HTTPException(status_code=400, detail="OBSIDIAN_VAULT_PATH not set")

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
    vault = os.environ.get("OBSIDIAN_VAULT_PATH")
    if not vault:
        raise HTTPException(status_code=400, detail="OBSIDIAN_VAULT_PATH not set")

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
