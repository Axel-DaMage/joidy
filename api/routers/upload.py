import logging
import re
import uuid
from pathlib import Path

import aiofiles
from config import settings
from fastapi import APIRouter, File, HTTPException, UploadFile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["upload"])

ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
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

# Text-based MIME types have no reliable magic bytes; they are validated by
# ensuring the payload decodes as UTF-8 with no NUL bytes (binary indicator).
_TEXT_TYPES = {
    "text/plain",
    "text/markdown",
    "text/x-markdown",
    "application/json",
    "application/rtf",
}

# Stored-extension allowlist keyed by *validated* MIME type. The on-disk
# extension is derived from the verified content_type — never from the
# user-supplied filename — so a text/plain payload can no longer be saved as
# .html and later served inline as text/html (stored XSS, #1279).
_MIME_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/avif": ".avif",
    "application/pdf": ".pdf",
    "text/plain": ".txt",
    "text/markdown": ".md",
    "text/x-markdown": ".md",
    "application/json": ".json",
    "application/rtf": ".rtf",
    "application/msword": ".doc",
    "application/vnd.ms-excel": ".xls",
    "application/vnd.ms-powerpoint": ".ppt",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
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


def _matches_magic(content: bytes, content_type: str) -> bool:
    """Verify that ``content`` starts with the magic bytes expected for
    ``content_type``. Returns ``True`` when the signature matches (or the type
    is text-based and decodes cleanly), ``False`` otherwise."""
    # Text-based types: validate as UTF-8 text without NUL bytes (binary marker).
    if content_type in _TEXT_TYPES:
        if b"\x00" in content:
            return False
        try:
            content.decode("utf-8")
        except UnicodeDecodeError:
            return False
        return True

    signatures = _magic_signatures().get(content_type)
    if not signatures:
        # Unknown type with no known signature: cannot verify, reject.
        return False

    for sig, offset in signatures:
        if content[offset : offset + len(sig)] == sig:
            # WebP: RIFF....WEBP — also confirm the WEBP fourcc at offset 8.
            if content_type == "image/webp" and content[8:12] != b"WEBP":
                continue
            # AVIF: ISOBMFF ftyp box — confirm brand is avif/avis at offset 8.
            if content_type == "image/avif" and content[8:12] not in (b"avif", b"avis"):
                continue
            return True
    return False


def _magic_signatures() -> dict[str, list[tuple[bytes, int]]]:
    """Map MIME type to a list of ``(magic_bytes, offset)`` candidates."""
    return {
        "image/png": [(b"\x89PNG\r\n\x1a\n", 0)],
        "image/jpeg": [(b"\xff\xd8\xff", 0)],
        "image/gif": [(b"GIF87a", 0), (b"GIF89a", 0)],
        "image/webp": [(b"RIFF", 0)],
        "image/avif": [(b"ftyp", 4)],
        "application/pdf": [(b"%PDF", 0)],
        # OLE2 compound document (legacy Office formats).
        "application/msword": [(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", 0)],
        "application/vnd.ms-excel": [(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", 0)],
        "application/vnd.ms-powerpoint": [(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", 0)],
        # OOXML formats are ZIP containers.
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [(b"PK\x03\x04", 0)],
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [(b"PK\x03\x04", 0)],
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": [(b"PK\x03\x04", 0)],
    }


async def _save_upload(file: UploadFile, max_bytes: int, allowed: set[str]) -> dict:
    upload_path = _ensure_upload_dir()

    content_type = file.content_type or "application/octet-stream"
    if content_type not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de archivo no permitido: {content_type}",
        )

    content = await file.read()
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail="Archivo demasiado grande")

    if not _matches_magic(content, content_type):
        raise HTTPException(
            status_code=400,
            detail="El contenido del archivo no coincide con el tipo declarado",
        )

    safe_name = _secure_filename(file.filename)
    # Extension comes from the validated MIME type, never the filename (#1279):
    # "evil.html" declared as text/plain is stored as "evil.txt". We keep only
    # the sanitized stem so a hostile suffix can't survive into the URL.
    ext = _MIME_EXTENSIONS.get(content_type, ".bin")
    stem = Path(safe_name).stem or "file"
    safe_name = f"{stem}{ext}"

    unique_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"
    dest = upload_path / unique_name

    async with aiofiles.open(dest, "wb") as f:
        await f.write(content)

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
    return await _save_upload(file, settings.upload_max_image_bytes, ALLOWED_IMAGE_TYPES)


@router.post("/file")
async def upload_file(file: UploadFile = File(...)):
    """Sube un archivo adjunto y devuelve la URL pública."""
    return await _save_upload(file, settings.upload_max_file_bytes, ALLOWED_FILE_TYPES)
