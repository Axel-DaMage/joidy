"""
Export endpoints for notes.
"""

import io
import zipfile
from datetime import datetime
from typing import Iterator

from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from models.note import Note, NoteTag
from services.auth_service import get_current_user
from sqlalchemy.orm import Session, selectinload

router = APIRouter(prefix="/export", tags=["export"])

EXPORT_MAX_NOTES = 5000
EXPORT_BATCH_SIZE = 100


def iter_notes_batched(db: Session, limit: int = EXPORT_MAX_NOTES) -> Iterator[Note]:
    """Yield notes in batches using SQL pagination so that not all notes (and
    their tag relationships) are loaded into memory at once.

    Each batch is expunged from the session after it has been consumed, freeing
    the associated ORM objects before the next batch is fetched.
    """
    offset = 0
    remaining = limit
    while remaining > 0:
        batch_size = min(EXPORT_BATCH_SIZE, remaining)
        batch = (
            db.query(Note)
            .options(selectinload(Note.tags).selectinload(NoteTag.tag))
            .order_by(Note.created_at.desc())
            .limit(batch_size)
            .offset(offset)
            .all()
        )
        if not batch:
            break
        for note in batch:
            yield note
        # Detach the consumed batch from the session so it can be garbage
        # collected before the next batch is loaded.
        db.expunge_all()
        offset += len(batch)
        remaining -= len(batch)


def note_to_markdown(note: Note) -> str:
    """Convert a note to markdown format."""
    lines = [f"# {note.title}", ""]

    if note.tags:
        tags = [nt.tag.name for nt in note.tags if nt.tag]
        if tags:
            lines.append(f"Tags: {', '.join(tags)}")

    lines.append(f"Created: {note.created_at.isoformat()}")
    lines.append(f"Updated: {note.updated_at.isoformat()}")
    lines.append("")
    lines.append(note.content or "")
    return "\n".join(lines)


def _html_escape(text: str) -> str:
    """Escape HTML special characters to prevent XSS."""
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#x27;")


def note_to_html(note: Note) -> str:
    """Convert a note to HTML format."""
    content = _html_escape(note.content or "")
    title = _html_escape(note.title or "")
    tags = [_html_escape(nt.tag.name) for nt in note.tags if nt.tag]

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; line-height: 1.6; }}
    h1 {{ color: #c8a96e; }}
    .meta {{ color: #666; font-size: 0.9em; }}
    .tags {{ margin: 10px 0; }}
    .tag {{ background: #eee; padding: 2px 8px; border-radius: 4px; font-size: 0.85em; }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <div class="meta">
    <div>Created: {note.created_at.isoformat()}</div>
    <div>Updated: {note.updated_at.isoformat()}</div>
  </div>
  {"<div class='tags'>" + "".join(f"<span class='tag'>{t}</span>" for t in tags) + "</div>" if tags else ""}
  <hr>
  <div class="content">{content}</div>
</body>
</html>"""
    return html


@router.get("/notes/markdown")
def export_notes_markdown(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    """Export all notes as a single markdown file."""
    if db.query(Note).count() == 0:
        raise HTTPException(status_code=404, detail="No notes to export")

    def generate():
        first = True
        for note in iter_notes_batched(db):
            if not first:
                yield b"\n---\n\n"
            first = False
            yield note_to_markdown(note).encode("utf-8")

    return StreamingResponse(
        generate(),
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename=joidy-export-{datetime.now().date()}.md"}
    )


@router.get("/notes/html")
def export_notes_html(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    """Export all notes as a single HTML file."""
    if db.query(Note).count() == 0:
        raise HTTPException(status_code=404, detail="No notes to export")

    export_date = datetime.now().date()
    export_iso = datetime.now().isoformat()

    def generate():
        yield f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Joidy Export - {export_date}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; }}
    .note {{ margin-bottom: 60px; padding-bottom: 40px; border-bottom: 1px solid #eee; }}
  </style>
</head>
<body>
  <h1>Joidy Notes Export</h1>
  <p>Exported on {export_iso}</p>
  <hr>
""".encode("utf-8")
        for note in iter_notes_batched(db):
            yield f'<div class="note">{note_to_html(note)}</div>'.encode("utf-8")
        yield b"\n</body>\n</html>"

    return StreamingResponse(
        generate(),
        media_type="text/html",
        headers={"Content-Disposition": f"attachment; filename=joidy-export-{export_date}.html"}
    )


@router.get("/notes/zip")
def export_notes_zip(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    """Export all notes as individual markdown files in a ZIP."""
    if db.query(Note).count() == 0:
        raise HTTPException(status_code=404, detail="No notes to export")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # Notes are fetched in batches so that not all notes (and their tag
        # relationships) are held in memory at once. The ZIP archive itself is
        # still assembled in a buffer, but the per-note ORM objects are released
        # between batches.
        for note in iter_notes_batched(db):
            safe_title = "".join(c for c in note.title if c.isalnum() or c in " -_").strip()[:50]
            if not safe_title:
                safe_title = "unnamed"
            filename = f"{note.id}_{safe_title}.md"
            zf.writestr(filename, note_to_markdown(note).encode("utf-8"))

    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=joidy-notes-{datetime.now().date()}.zip"}
    )
