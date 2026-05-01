import re
from typing import Optional

from sqlalchemy.orm import Session

from models.note import Note, NoteLink, NoteTag, Tag
from services.gamification_engine import process_event
from services.skill_tree import sync_skills
from services.tag_graph import rebuild_tag_cooccurrences
from services.goal_service import sync_goals_from_note


def note_to_response(note: Note) -> dict:
    return {
        "id": note.id,
        "title": note.title,
        "content": note.content,
        "source": note.source,
        "source_path": note.source_path,
        "tags": [nt.tag.name for nt in note.tags if nt.tag],
        "created_at": note.created_at.isoformat() + "Z",
        "updated_at": note.updated_at.isoformat() + "Z",
    }


def get_or_create_tag(db: Session, name: str) -> Tag:
    normalized = name.lower().strip()
    tag = db.query(Tag).filter(Tag.name == normalized).first()
    if not tag:
        tag = Tag(name=normalized)
        db.add(tag)
        db.flush()
    return tag


def sync_note_links(db: Session, source_note_id: int, content: str) -> None:
    """Parse WikiLinks and update note_links table for a note."""
    db.query(NoteLink).filter(NoteLink.source_note_id == source_note_id).delete()

    links = re.findall(r"\[\[\s*([^\]|]+?)\s*(?:\|[^\]]+)?\]\]", content)
    for title in set(links):
        target = db.query(Note).filter(Note.title.ilike(title.strip())).first()
        if target:
            db.add(NoteLink(source_note_id=source_note_id, target_note_id=target.id))

    db.flush()


def create_note(
    db: Session,
    *,
    title: str,
    content: str,
    tags: list[str],
    source: str,
    source_path: Optional[str],
):
    note = Note(title=title, content=content, source=source, source_path=source_path)
    db.add(note)
    db.flush()

    for tag_name in tags:
        tag = get_or_create_tag(db, tag_name)
        db.add(NoteTag(note_id=note.id, tag_id=tag.id, source="manual"))
        process_event(db, "tag_added")

    event = "note_imported_obsidian" if source == "obsidian" else "note_created"
    gami = process_event(db, event, {"note_id": note.id})

    sync_note_links(db, note.id, content)
    sync_goals_from_note(db, note.id, content)
    rebuild_tag_cooccurrences(db)

    db.commit()
    db.refresh(note)
    sync_skills(db)

    return note, gami


def update_note(
    db: Session,
    note_id: int,
    *,
    title: Optional[str] = None,
    content: Optional[str] = None,
    tags: Optional[list[str]] = None,
    source_path: Optional[str] = None,
    source: Optional[str] = None,
):
    note = db.query(Note).filter(Note.id == note_id).first()
    if note is None:
        return None, None

    gami = None
    if title is not None:
        note.title = title
    if source_path is not None:
        note.source_path = source_path
    if source is not None:
        note.source = source
    if content is not None:
        old_len = len(note.content)
        note.content = content
        if abs(len(content) - old_len) > 50:
            gami = process_event(db, "note_edited", {"note_id": note.id})
    if tags is not None:
        db.query(NoteTag).filter(NoteTag.note_id == note_id).delete()
        db.flush()
        for tag_name in tags:
            tag = get_or_create_tag(db, tag_name)
            db.add(NoteTag(note_id=note.id, tag_id=tag.id, source="manual"))

    if gami is None:
        gami = process_event(db, "note_edited", {"note_id": note.id})

    if content is not None:
        sync_note_links(db, note.id, content)
        sync_goals_from_note(db, note.id, content)
    if tags is not None:
        rebuild_tag_cooccurrences(db)

    db.commit()
    db.refresh(note)
    sync_skills(db)

    return note, gami


def delete_note(db: Session, note_id: int) -> bool:
    note = db.query(Note).filter(Note.id == note_id).first()
    if note is None:
        return False

    db.delete(note)
    rebuild_tag_cooccurrences(db)
    db.commit()
    sync_skills(db)
    return True


def accept_ai_tag(db: Session, note_id: int, tag_name: str):
    note = db.query(Note).filter(Note.id == note_id).first()
    if note is None:
        return None, None

    tag = get_or_create_tag(db, tag_name)
    existing = db.query(NoteTag).filter(NoteTag.note_id == note_id, NoteTag.tag_id == tag.id).first()
    if not existing:
        db.add(NoteTag(note_id=note.id, tag_id=tag.id, source="ai", confidence=0.9))
        rebuild_tag_cooccurrences(db)

    gami = process_event(db, "tag_accepted_ai", {"note_id": note_id, "tag": tag_name})
    db.commit()
    sync_skills(db)
    return tag, gami


def list_backlinks(db: Session, note_id: int) -> list[Note]:
    return (
        db.query(Note)
        .join(NoteLink, NoteLink.source_note_id == Note.id)
        .filter(NoteLink.target_note_id == note_id)
        .all()
    )
