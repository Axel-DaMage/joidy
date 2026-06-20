import os
import re
from typing import Optional

from sqlalchemy.orm import Session, selectinload

from models.note import Note, NoteLink, NoteTag, Tag
from services.gamification_engine import process_event
from services.sanitizer import sanitize_content, sanitize_tag, sanitize_title
from services.skill_tree import sync_skills, sync_skills_for_tags
from services.tag_graph import rebuild_tag_cooccurrences, sync_tag_cooccurrences_for_tags
from services.goal_service import sync_goals_from_note
from services.response_cache import clear_api_caches


def rebuild_derived_data(db: Session) -> None:
    """Rebuild the derived tag graph and skill table after bulk note imports."""
    rebuild_tag_cooccurrences(db)
    sync_skills(db)


def write_to_vault(note: Note) -> bool:
    """Write note content back to the vault file if source_path is set."""
    if not note.source_path:
        return False
    vault_path = os.environ.get("VAULT_PATH", "")
    if not vault_path:
        return False
    try:
        vault = os.path.abspath(vault_path)
        full_path = os.path.abspath(note.source_path)
        if not full_path.startswith(vault):
            return False
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(note.content)
        return True
    except Exception:
        return False


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
    rebuild_derived_data: bool = True,
):
    title = sanitize_title(title)
    content = sanitize_content(content)
    tags = [sanitize_tag(t) for t in tags if sanitize_tag(t)]
    note = Note(title=title, content=content, source=source, source_path=source_path)
    db.add(note)
    db.flush()
    touched_tag_ids: set[int] = set()

    for tag_name in tags:
        tag = get_or_create_tag(db, tag_name)
        db.add(NoteTag(note_id=note.id, tag_id=tag.id, source="manual"))
        touched_tag_ids.add(tag.id)
        process_event(db, "tag_added")

    event = "note_imported_obsidian" if source == "obsidian" else "note_created"
    gami = process_event(db, event, {"note_id": note.id})

    sync_note_links(db, note.id, content)
    sync_goals_from_note(db, note.id, content)
    if rebuild_derived_data:
        sync_tag_cooccurrences_for_tags(db, touched_tag_ids)

    db.commit()
    db.refresh(note)
    if rebuild_derived_data:
        sync_skills_for_tags(db, touched_tag_ids)
    if source_path:
        write_to_vault(note)
    clear_api_caches()

    try:
        from routers.websocket import broadcast_note_created
        broadcast_note_created(note.id, note.title)
    except Exception:
        pass

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
    rebuild_derived_data: bool = True,
):
    note = db.query(Note).filter(Note.id == note_id).first()
    if note is None:
        return None, None

    gami = None
    touched_tag_ids: set[int] = set()

    if title is not None:
        note.title = sanitize_title(title)
    if source_path is not None:
        note.source_path = source_path
    if source is not None:
        note.source = source
    if content is not None:
        content = sanitize_content(content)
        old_len = len(note.content)
        note.content = content
        if abs(len(content) - old_len) > 50:
            gami = process_event(db, "note_edited", {"note_id": note.id})
    if tags is not None:
        touched_tag_ids = {tag_id for tag_id, in db.query(NoteTag.tag_id).filter(NoteTag.note_id == note_id).all()}
        db.query(NoteTag).filter(NoteTag.note_id == note_id).delete()
        db.flush()
        for tag_name in tags:
            clean_tag = sanitize_tag(tag_name)
            if not clean_tag:
                continue
            tag = get_or_create_tag(db, clean_tag)
            db.add(NoteTag(note_id=note.id, tag_id=tag.id, source="manual"))
            touched_tag_ids.add(tag.id)

    if gami is None:
        gami = process_event(db, "note_edited", {"note_id": note.id})

    if content is not None:
        sync_note_links(db, note.id, content)
        sync_goals_from_note(db, note.id, content)
    if tags is not None:
        if rebuild_derived_data:
            sync_tag_cooccurrences_for_tags(db, touched_tag_ids)

    db.commit()
    db.refresh(note)
    if rebuild_derived_data and touched_tag_ids:
        sync_skills_for_tags(db, touched_tag_ids)
    if content is not None:
        write_to_vault(note)
    clear_api_caches()

    try:
        from routers.websocket import broadcast_note_updated
        broadcast_note_updated(note.id, note.title)
    except Exception:
        pass

    return note, gami


def delete_note(db: Session, note_id: int) -> bool:
    note = db.query(Note).filter(Note.id == note_id).first()
    if note is None:
        return False

    touched_tag_ids = {nt.tag_id for nt in note.tags}
    db.delete(note)
    sync_tag_cooccurrences_for_tags(db, touched_tag_ids)
    db.commit()
    sync_skills_for_tags(db, touched_tag_ids)
    clear_api_caches()
    return True


def accept_ai_tag(db: Session, note_id: int, tag_name: str):
    note = db.query(Note).filter(Note.id == note_id).first()
    if note is None:
        return None, None

    tag = get_or_create_tag(db, tag_name)
    existing = db.query(NoteTag).filter(NoteTag.note_id == note_id, NoteTag.tag_id == tag.id).first()
    if not existing:
        db.add(NoteTag(note_id=note.id, tag_id=tag.id, source="ai", confidence=0.9))
        sync_tag_cooccurrences_for_tags(db, {tag.id})

    gami = process_event(db, "tag_accepted_ai", {"note_id": note_id, "tag": tag_name})
    db.commit()
    sync_skills_for_tags(db, {tag.id})
    clear_api_caches()
    return tag, gami


def list_backlinks(db: Session, note_id: int) -> list[Note]:
    return (
        db.query(Note)
        .join(NoteLink, NoteLink.source_note_id == Note.id)
        .options(selectinload(Note.tags).selectinload(NoteTag.tag))
        .filter(NoteLink.target_note_id == note_id)
        .all()
    )
