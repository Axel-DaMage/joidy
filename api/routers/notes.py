from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload

from database import get_db
from models.note import EmbeddingFailure, Note, NoteTag, Tag
from services.embedding_service import get_retryable_embedding_notes, trigger_embedding
from services.note_service import (
    accept_ai_tag as accept_ai_tag_service,
    create_note as create_note_service,
    delete_note as delete_note_service,
    list_backlinks as list_backlinks_service,
    note_to_response,
    rebuild_derived_data as rebuild_note_derived_data,
    update_note as update_note_service,
)

router = APIRouter(prefix="/notes", tags=["notes"])


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


def _is_truthy_header(value: str | None) -> bool:
    return value is not None and value.lower() in {"1", "true", "yes", "on"}


@router.get("/")
def list_notes(
    skip: int = 0,
    limit: int = 1000,
    tag: Optional[str] = None,
    source_path: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Note).options(selectinload(Note.tags).selectinload(NoteTag.tag))
    if tag:
        query = query.join(NoteTag).join(Tag).filter(Tag.name == tag.lower())
    if source_path:
        query = query.filter(Note.source_path == source_path)
    notes = query.order_by(Note.created_at.desc()).offset(skip).limit(limit).all()
    return [note_to_response(n) for n in notes]


@router.get("/{note_id}")
def get_note(note_id: int, db: Session = Depends(get_db)):
    note = (
        db.query(Note)
        .options(selectinload(Note.tags).selectinload(NoteTag.tag))
        .filter(Note.id == note_id)
        .first()
    )
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return note_to_response(note)


@router.post("/", status_code=201)
def create_note(
    data: NoteCreate,
    background_tasks: BackgroundTasks,
    x_bulk_import: str | None = Header(default=None, alias="X-Bulk-Import"),
    db: Session = Depends(get_db),
):
    note, gami = create_note_service(
        db,
        title=data.title,
        content=data.content,
        tags=data.tags,
        source=data.source,
        source_path=data.source_path,
        rebuild_derived_data=not _is_truthy_header(x_bulk_import),
    )
    background_tasks.add_task(trigger_embedding, note.id, note.content)
    return {**note_to_response(note), "gamification": vars(gami)}


@router.put("/{note_id}")
def update_note(
    note_id: int,
    data: NoteUpdate,
    background_tasks: BackgroundTasks,
    x_bulk_import: str | None = Header(default=None, alias="X-Bulk-Import"),
    db: Session = Depends(get_db),
):
    note, gami = update_note_service(
        db,
        note_id,
        title=data.title,
        content=data.content,
        tags=data.tags,
        source_path=data.source_path,
        source=data.source,
        rebuild_derived_data=not _is_truthy_header(x_bulk_import),
    )
    if note is None or gami is None:
        raise HTTPException(status_code=404, detail="Note not found")
    background_tasks.add_task(trigger_embedding, note.id, note.content)
    return {**note_to_response(note), "gamification": vars(gami)}


@router.post("/rebuild-derived", status_code=202)
def rebuild_derived(db: Session = Depends(get_db)):
    rebuild_note_derived_data(db)
    return {"status": "ok"}


@router.delete("/{note_id}", status_code=204)
def delete_note(note_id: int, db: Session = Depends(get_db)):
    deleted = delete_note_service(db, note_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Note not found")


@router.post("/{note_id}/accept-tag")
def accept_ai_tag(note_id: int, tag_name: str, db: Session = Depends(get_db)):
    tag, gami = accept_ai_tag_service(db, note_id, tag_name)
    if tag is None or gami is None:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"tag": tag_name, "gamification": vars(gami)}


@router.get("/{note_id}/backlinks")
def get_backlinks(note_id: int, db: Session = Depends(get_db)):
    backlinks = list_backlinks_service(db, note_id)
    return [note_to_response(n) for n in backlinks]


@router.post("/embeddings/retry-failed")
def retry_failed_embeddings(
    background_tasks: BackgroundTasks,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    failures = get_retryable_embedding_notes(db, limit=limit)
    queued = 0
    for note in failures:
        background_tasks.add_task(trigger_embedding, note.id, note.content)
        queued += 1

    db.commit()
    return {"queued": queued, "remaining_failures": db.query(EmbeddingFailure).count()}
