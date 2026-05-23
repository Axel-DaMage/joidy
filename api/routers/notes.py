from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Header, Query
from pydantic import BaseModel, field_validator, model_validator
from sqlalchemy.orm import Session, selectinload

from database import get_db
from models.note import EmbeddingFailure, Note, NoteTag, Tag
from services.embedding_service import (
    get_dead_letter_entries,
    get_retryable_embedding_notes,
    purge_dead_letters,
    reset_dead_letter_entry,
    trigger_embedding,
)
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

ALLOWED_SOURCES = {"joidy", "obsidian", "api", "import"}


class NoteCreate(BaseModel):
    """Schema for creating a new note."""
    title: str
    content: str = ""
    tags: list[str] = []
    source: str = "joidy"
    source_path: Optional[str] = None

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Title cannot be empty")
        if len(v) > 500:
            raise ValueError("Title must be 500 characters or fewer")
        return v

    @field_validator("content")
    @classmethod
    def content_max_length(cls, v: str) -> str:
        if len(v) > 500_000:
            raise ValueError("Content must be 500,000 characters or fewer")
        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        if len(v) > 50:
            raise ValueError("Maximum 50 tags per note")
        return [t.strip().lower() for t in v if t.strip() and len(t.strip()) <= 100]

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in ALLOWED_SOURCES:
            raise ValueError(f"Source must be one of: {', '.join(sorted(ALLOWED_SOURCES))}")
        return v


class NoteUpdate(BaseModel):
    """Schema for updating an existing note."""
    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[list[str]] = None
    source_path: Optional[str] = None
    source: Optional[str] = None

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("Title cannot be empty")
        if len(v) > 500:
            raise ValueError("Title must be 500 characters or fewer")
        return v

    @field_validator("content")
    @classmethod
    def content_max_length(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 500_000:
            raise ValueError("Content must be 500,000 characters or fewer")
        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        if len(v) > 50:
            raise ValueError("Maximum 50 tags per note")
        return [t.strip().lower() for t in v if t.strip() and len(t.strip()) <= 100]

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip().lower()
        if v not in ALLOWED_SOURCES:
            raise ValueError(f"Source must be one of: {', '.join(sorted(ALLOWED_SOURCES))}")
        return v


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


@router.get("/embeddings/dead-letters")
def list_dead_letters(limit: int = 50, db: Session = Depends(get_db)):
    """List embedding failures that exceeded max retry attempts."""
    return get_dead_letter_entries(db, limit=limit)


@router.post("/embeddings/dead-letters/{note_id}/reset")
def reset_dead_letter(note_id: int, db: Session = Depends(get_db)):
    """Reset a dead-lettered embedding failure so it can be retried."""
    if not reset_dead_letter_entry(db, note_id):
        raise HTTPException(status_code=404, detail="Dead letter entry not found")
    return {"status": "reset", "note_id": note_id}


@router.delete("/embeddings/dead-letters")
def purge_all_dead_letters(db: Session = Depends(get_db)):
    """Remove all dead-lettered embedding failures."""
    count = purge_dead_letters(db)
    return {"purged": count}
