import logging
import mimetypes
import re
import uuid
from pathlib import Path

from config import settings
from fastapi import APIRouter, File, HTTPException, UploadFile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["upload"])

ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/svg+xml",
    "image/avif",
}

ALLOWED_FILE_TYPES = {
    "application/pdf",
    "text/plain",
    "text/markdown",
    "text/x-markdown",
    "application/json",
    "application/rtf",
    "application/msword",
    "application/vnd.ms-excel",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def _ensure_upload_dir() -> Path:
    path = Path(settings.upload_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _secure_filename(name: str | None) -> str:
    if not name:
        return "file"
    base = Path(name).name
    base = re.sub(r"[^a-zA-Z0-9_.-]", "_", base)
    if not base:
        base = "file"
    return base


def _save_upload(file: UploadFile, max_bytes: int, allowed: set[str]) -> dict:
    upload_path = _ensure_upload_dir()

    content_type = file.content_type or "application/octet-stream"
    if content_type not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de archivo no permitido: {content_type}",
        )

    content = file.file.read()
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail="Archivo demasiado grande")

    safe_name = _secure_filename(file.filename)
    ext = Path(file.filename or "").suffix
    if not ext:
        ext = mimetypes.guess_extension(content_type) or ".bin"
    if not safe_name.endswith(ext):
        safe_name = f"{safe_name}{ext}"

    unique_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"
    dest = upload_path / unique_name

    with open(dest, "wb") as f:
        f.write(content)

    logger.info("[upload] saved %s (%s bytes) -> %s", content_type, len(content), dest)

    return {
        "url": f"/uploads/{unique_name}",
        "filename": safe_name,
        "mime": content_type,
        "size": len(content),
    }


@router.post("/image")
async def upload_image(file: UploadFile = File(...)):
    """Sube una imagen y devuelve la URL pública."""
    return _save_upload(file, settings.upload_max_image_bytes, ALLOWED_IMAGE_TYPES)


@router.post("/file")
async def upload_file(file: UploadFile = File(...)):
    """Sube un archivo adjunto y devuelve la URL pública."""
    return _save_upload(file, settings.upload_max_file_bytes, ALLOWED_FILE_TYPES)
