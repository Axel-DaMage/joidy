import re
import logging
from datetime import datetime, timedelta
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db, SessionLocal
from models.note import EmbeddingFailure, Note, NoteTag, Tag
from services.gamification_engine import process_event
from services.embedding_retry import compute_retry_delay_seconds
from services.skill_tree import sync_skills
from services.tag_graph import rebuild_tag_cooccurrences
from config import settings

router = APIRouter(prefix="/notes", tags=["notes"])
logger = logging.getLogger(__name__)


class NoteCreate(BaseModel):
    title: str
    content: str = ""
    tags: list[str] = []
    source: str = "joidy"
    source_path: Optional[str] = None


class NoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[list[str]] = None
    source_path: Optional[str] = None
    source: Optional[str] = None


class NoteResponse(BaseModel):
    id: int
    title: str
    content: str
    source: str
    tags: list[str]
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


def _note_to_response(note: Note) -> dict:
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


def _get_or_create_tag(db: Session, name: str) -> Tag:
    tag = db.query(Tag).filter(Tag.name == name.lower().strip()).first()
    if not tag:
        tag = Tag(name=name.lower().strip())
        db.add(tag)
        db.flush()
    return tag


def _sync_note_links(db: Session, source_note_id: int, content: str):
    """Parse [[WikiLinks]] and update note_links table."""
    from models.note import NoteLink, Note
    
    # 1. Clear existing links
    db.query(NoteLink).filter(NoteLink.source_note_id == source_note_id).delete()
    
    # 2. Extract links
    # Supports [[Title]] or [[Title|Alias]]
    # Handles leading/trailing spaces in title
    links = re.findall(r"\[\[\s*([^\]|]+?)\s*(?:\|[^\]]+)?\]\]", content)
    
    for title in set(links):
        # Find target note by title (case-insensitive)
        target = db.query(Note).filter(Note.title.ilike(title.strip())).first()
        if target:
            db.add(NoteLink(source_note_id=source_note_id, target_note_id=target.id))
    
    db.flush()


async def _trigger_embedding(note_id: int, content: str):
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.ai_service_url}/embed",
                json={"note_id": note_id, "content": content},
            )
            response.raise_for_status()
        _clear_embedding_failure(note_id)
    except Exception as exc:
        _record_embedding_failure(note_id, str(exc))
        logger.exception("Embedding failed for note_id=%s", note_id)


def _record_embedding_failure(note_id: int, error_message: str) -> None:
    with SessionLocal() as db:
        failure = db.query(EmbeddingFailure).filter(EmbeddingFailure.note_id == note_id).first()
        if failure is None:
            failure = EmbeddingFailure(note_id=note_id, attempts=0)
            db.add(failure)

        failure.attempts += 1
        failure.last_error = error_message[:2000]
        delay = compute_retry_delay_seconds(failure.attempts, settings.embedding_retry_base_seconds)
        failure.next_retry_at = datetime.utcnow() + timedelta(seconds=delay)
        db.commit()


def _clear_embedding_failure(note_id: int) -> None:
    with SessionLocal() as db:
        db.query(EmbeddingFailure).filter(EmbeddingFailure.note_id == note_id).delete()
        db.commit()


@router.get("/")
def list_notes(
    skip: int = 0,
    limit: int = 1000,
    tag: Optional[str] = None,
    source_path: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Note)
    if tag:
        query = query.join(NoteTag).join(Tag).filter(Tag.name == tag.lower())
    if source_path:
        query = query.filter(Note.source_path == source_path)
    notes = query.order_by(Note.created_at.desc()).offset(skip).limit(limit).all()
    return [_note_to_response(n) for n in notes]


@router.get("/{note_id}")
def get_note(note_id: int, db: Session = Depends(get_db)):
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return _note_to_response(note)


@router.post("/", status_code=201)
async def create_note(
    data: NoteCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    note = Note(title=data.title, content=data.content, source=data.source, source_path=data.source_path)
    db.add(note)
    db.flush()

    for tag_name in data.tags:
        tag = _get_or_create_tag(db, tag_name)
        note_tag = NoteTag(note_id=note.id, tag_id=tag.id, source="manual")
        db.add(note_tag)
        process_event(db, "tag_added")  # XP recorded in DB; final gami returned below

    event = "note_imported_obsidian" if data.source == "obsidian" else "note_created"
    gami = process_event(db, event, {"note_id": note.id})
    
    _sync_note_links(db, note.id, data.content)
    rebuild_tag_cooccurrences(db)
    
    db.commit()
    db.refresh(note)

    sync_skills(db)
    background_tasks.add_task(_trigger_embedding, note.id, note.content)

    return {**_note_to_response(note), "gamification": vars(gami)}


@router.put("/{note_id}")
async def update_note(
    note_id: int,
    data: NoteUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    gami = None
    if data.title is not None:
        note.title = data.title
    if data.source_path is not None:
        note.source_path = data.source_path
    if data.source is not None:
        note.source = data.source
    if data.content is not None:
        old_len = len(note.content)
        note.content = data.content
        if abs(len(data.content) - old_len) > 50:
            gami = process_event(db, "note_edited", {"note_id": note.id})
    if data.tags is not None:
        db.query(NoteTag).filter(NoteTag.note_id == note_id).delete()
        db.flush()  # Ensure delete completes before inserting new tags (FK + PK conflict prevention)
        for tag_name in data.tags:
            tag = _get_or_create_tag(db, tag_name)
            db.add(NoteTag(note_id=note.id, tag_id=tag.id, source="manual"))

    if gami is None:
        gami = process_event(db, "note_edited", {"note_id": note.id})

    if data.content is not None:
        _sync_note_links(db, note.id, data.content)

    if data.tags is not None:
        rebuild_tag_cooccurrences(db)

    db.commit()
    db.refresh(note)
    sync_skills(db)
    background_tasks.add_task(_trigger_embedding, note.id, note.content)

    return {**_note_to_response(note), "gamification": vars(gami)}


@router.delete("/{note_id}", status_code=204)
def delete_note(note_id: int, db: Session = Depends(get_db)):
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    db.delete(note)
    rebuild_tag_cooccurrences(db)
    db.commit()
    sync_skills(db)


@router.post("/{note_id}/accept-tag")
def accept_ai_tag(note_id: int, tag_name: str, db: Session = Depends(get_db)):
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    tag = _get_or_create_tag(db, tag_name)
    existing = db.query(NoteTag).filter(NoteTag.note_id == note_id, NoteTag.tag_id == tag.id).first()
    if not existing:
        db.add(NoteTag(note_id=note.id, tag_id=tag.id, source="ai", confidence=0.9))
        rebuild_tag_cooccurrences(db)

    gami = process_event(db, "tag_accepted_ai", {"note_id": note_id, "tag": tag_name})
    db.commit()
    sync_skills(db)

    return {"tag": tag_name, "gamification": vars(gami)}


@router.get("/{note_id}/backlinks")
def get_backlinks(note_id: int, db: Session = Depends(get_db)):
    """Returns a list of notes that link to this one."""
    from models.note import NoteLink, Note
    
    backlinking_notes = db.query(Note).join(NoteLink, NoteLink.source_note_id == Note.id)\
                                      .filter(NoteLink.target_note_id == note_id).all()
    
    return [_note_to_response(n) for n in backlinking_notes]


@router.post("/embeddings/retry-failed")
async def retry_failed_embeddings(
    background_tasks: BackgroundTasks,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    now = datetime.utcnow()
    failures = (
        db.query(EmbeddingFailure)
        .filter(EmbeddingFailure.attempts < settings.embedding_retry_max_attempts)
        .filter((EmbeddingFailure.next_retry_at.is_(None)) | (EmbeddingFailure.next_retry_at <= now))
        .order_by(EmbeddingFailure.updated_at.asc())
        .limit(max(1, min(limit, 200)))
        .all()
    )

    queued = 0
    for failure in failures:
        note = db.query(Note).filter(Note.id == failure.note_id).first()
        if not note:
            db.delete(failure)
            continue
        background_tasks.add_task(_trigger_embedding, note.id, note.content)
        queued += 1

    db.commit()
    return {"queued": queued, "remaining_failures": db.query(EmbeddingFailure).count()}
