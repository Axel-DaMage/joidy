import os
import shutil
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/folders", tags=["folders"])

class FolderCreate(BaseModel):
    path: str

@router.post("/")
def create_folder(folder: FolderCreate):
    vault = os.environ.get("OBSIDIAN_VAULT_PATH")
    if not vault:
        raise HTTPException(status_code=400, detail="OBSIDIAN_VAULT_PATH not set")
    
    if ".." in folder.path or folder.path.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid path")

    full_path = os.path.join(vault, folder.path)
    if os.path.exists(full_path):
        raise HTTPException(status_code=400, detail="Folder already exists")
    
    try:
        os.makedirs(full_path, exist_ok=True)
        return {"status": "ok", "path": folder.path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{path:path}")
def delete_folder(path: str):
    vault = os.environ.get("OBSIDIAN_VAULT_PATH")
    if not vault:
        raise HTTPException(status_code=400, detail="OBSIDIAN_VAULT_PATH not set")
    
    if ".." in path or path.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid path")

    full_path = os.path.join(vault, path)
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="Folder not found")
    
    if not os.path.isdir(full_path):
        raise HTTPException(status_code=400, detail="Not a folder")
        
    try:
        shutil.rmtree(full_path)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
