"""
Export endpoints for notes.
"""

import io
import zipfile
from datetime import datetime

from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from models.note import Note
from sqlalchemy.orm import Session

router = APIRouter(prefix="/export", tags=["export"])


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


def note_to_html(note: Note) -> str:
    """Convert a note to HTML format."""
    content = (note.content or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    tags = [nt.tag.name for nt in note.tags if nt.tag]

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{note.title}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; line-height: 1.6; }}
    h1 {{ color: #c8a96e; }}
    .meta {{ color: #666; font-size: 0.9em; }}
    .tags {{ margin: 10px 0; }}
    .tag {{ background: #eee; padding: 2px 8px; border-radius: 4px; font-size: 0.85em; }}
  </style>
</head>
<body>
  <h1>{note.title}</h1>
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
def export_notes_markdown(db: Session = Depends(get_db)):
    """Export all notes as a single markdown file."""
    notes = db.query(Note).all()

    if not notes:
        raise HTTPException(status_code=404, detail="No notes to export")

    content = "\n---\n\n".join(note_to_markdown(n) for n in notes)

    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename=joidy-export-{datetime.now().date()}.md"}
    )


@router.get("/notes/html")
def export_notes_html(db: Session = Depends(get_db)):
    """Export all notes as a single HTML file."""
    notes = db.query(Note).all()

    if not notes:
        raise HTTPException(status_code=404, detail="No notes to export")

    html_parts = [note_to_html(n) for n in notes]
    full_html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Joidy Export - {datetime.now().date()}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; }}
    .note {{ margin-bottom: 60px; padding-bottom: 40px; border-bottom: 1px solid #eee; }}
  </style>
</head>
<body>
  <h1>Joidy Notes Export</h1>
  <p>Exported on {datetime.now().isoformat()}</p>
  <hr>
  {"".join(f'<div class="note">{h}</div>' for h in html_parts)}
</body>
</html>"""

    return StreamingResponse(
        io.BytesIO(full_html.encode("utf-8")),
        media_type="text/html",
        headers={"Content-Disposition": f"attachment; filename=joidy-export-{datetime.now().date()}.html"}
    )


@router.get("/notes/zip")
def export_notes_zip(db: Session = Depends(get_db)):
    """Export all notes as individual markdown files in a ZIP."""
    notes = db.query(Note).all()

    if not notes:
        raise HTTPException(status_code=404, detail="No notes to export")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for note in notes:
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
