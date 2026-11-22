import os
from datetime import UTC, datetime

from config import settings
from database import get_db
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Request, Response
from models.note import EmbeddingFailure, Note, NoteTag, Tag
from pydantic import BaseModel, Field, field_validator
from services.auth_service import verify_internal_token
from services.embedding_service import (
    get_dead_letter_entries,
    get_retryable_embedding_notes,
    purge_dead_letters,
    reset_dead_letter_entry,
    trigger_embedding,
)
from services.http_client import http_client
from services.note_service import (
    accept_ai_tag as accept_ai_tag_service,
)
from services.note_service import (
    create_note as create_note_service,
)
from services.note_service import (
    delete_note as delete_note_service,
)
from services.note_service import (
    get_or_create_tag,
    note_to_response,
)
from services.note_service import (
    list_backlinks as list_backlinks_service,
)
from services.note_service import (
    rebuild_derived_data as rebuild_note_derived_data,
)
from services.note_service import (
    update_note as update_note_service,
)
from services.pagination import add_pagination_headers
from services.sanitizer import MAX_TAG_LENGTH, sanitize_content, sanitize_tag, sanitize_title
from services.skill_tree import sync_skills_for_tags
from services.tag_graph import sync_tag_cooccurrences_for_tags
from services.vault_paths import normalize_source_path, resolve_confined_source_path
from sqlalchemy import text
from sqlalchemy.orm import Session, defer, selectinload

router = APIRouter(prefix="/notes", tags=["notes"])


ALLOWED_SOURCES = {"joidy", "obsidian", "api", "import"}
# Provenance only the internal service token may claim (#1332): a regular
# client asserting "obsidian" would trigger the vault_synced broadcast and
# the note_imported_obsidian XP event meant for real watcher traffic.
_INTERNAL_SOURCES = {"obsidian", "import"}


def _clean_tag_list(tags: list[str]) -> list[str]:
    """Normalize raw tag names through ``sanitize_tag``, drop empties and
    deduplicate (order-preserving). Single entry point so every tag-name
    input — note create/update, bulk ops — gets identical handling (#1322)."""
    seen: set[str] = set()
    deduped: list[str] = []
    for t in tags:
        if not isinstance(t, str):
            continue
        cleaned = sanitize_tag(t)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            deduped.append(cleaned)
    return deduped


class NoteCreate(BaseModel):
    """Schema for creating a new note."""

    title: str
    content: str = ""
    tags: list[str] = []
    source: str = "joidy"
    source_path: str | None = None

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        return sanitize_title(v)

    @field_validator("content")
    @classmethod
    def content_max_length(cls, v: str) -> str:
        return sanitize_content(v)

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        if len(v) > 50:
            raise ValueError("Maximum 50 tags per note")
        return _clean_tag_list(v)

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in ALLOWED_SOURCES:
            raise ValueError(f"Source must be one of: {', '.join(sorted(ALLOWED_SOURCES))}")
        return v


class NoteUpdate(BaseModel):
    """Schema for updating an existing note."""

    title: str | None = None
    content: str | None = None
    tags: list[str] | None = None
    source_path: str | None = None
    source: str | None = None

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return sanitize_title(v)

    @field_validator("content")
    @classmethod
    def content_max_length(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return sanitize_content(v)

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        if len(v) > 50:
            raise ValueError("Maximum 50 tags per note")
        return _clean_tag_list(v)

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


class BulkIds(BaseModel):
    # Bounded so a bulk request can't fan out into an unbounded DB query storm (#1322).
    ids: list[int] = Field(max_length=500)


class BulkTagRequest(BaseModel):
    ids: list[int] = Field(max_length=500)
    tags: list[str] = Field(max_length=50)

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        return _clean_tag_list(v)


def _is_truthy_header(value: str | None) -> bool:
    return value is not None and value.lower() in {"1", "true", "yes", "on"}


def _internal_service_request(request: Request) -> bool:
    """True when the caller authenticated with the INTERNAL_API_TOKEN.

    ``X-From-Vault``/``X-Bulk-Import`` change provenance and skip work
    (file-write checks, derived-graph rebuilds), so they are trust headers
    only the vault worker may send. Any other client presenting them has
    the headers ignored — the request proceeds as a normal note write,
    which applies the stricter validation path (#1332).
    """
    auth = request.headers.get("authorization") or ""
    scheme, _, token = auth.partition(" ")
    return scheme.lower() == "bearer" and verify_internal_token(token)


def _note_id_owning_resolved(db: Session, resolved: str) -> int | None:
    """Id of the note whose stored ``source_path`` resolves to ``resolved``.

    Compares realpaths, not strings, so symlink aliases of the same file can
    never belong to two different notes.
    """
    for note_id, stored in db.query(Note.id, Note.source_path).filter(Note.source_path.isnot(None)):
        if stored and resolve_confined_source_path(stored) == resolved:
            return note_id
    return None


def _validated_source_path(
    db: Session,
    source_path: str | None,
    *,
    note_id: int | None,
    writes_file: bool,
) -> None:
    """Reject an unsafe client-supplied ``source_path`` with a generic 400.

    The path must normalize onto the canonical vault domain and resolve,
    after ``realpath``, strictly inside the effective vault root as a ``.md``
    file outside hidden dirs (``.obsidian`` …) and ``_joidy/`` — so prefix
    confusion, traversal, symlink escapes, and Joidy/Obsidian internals are
    all refused (#1287, #1314).

    When the request could write the file (``writes_file`` — i.e. it did not
    come from the vault watcher), an already-existing target must be the
    note's own file: creations fall through to ``create_note``'s
    source_path dedup, and updates may only keep their own file — a client
    can never aim a write at a vault file no note owns.

    One generic detail for every rejection: distinguishing "outside vault"
    from "already exists" would leak a file-existence oracle (#1314).
    """
    if source_path is None:
        return
    normalized = normalize_source_path(source_path)
    if normalized is None:
        return
    resolved = resolve_confined_source_path(normalized)
    if resolved is None:
        raise HTTPException(status_code=400, detail="Invalid source_path")
    if writes_file and os.path.exists(resolved):
        owner_id = _note_id_owning_resolved(db, resolved)
        if owner_id is None or (note_id is not None and owner_id != note_id):
            raise HTTPException(status_code=400, detail="Invalid source_path")


@router.get("/")
def list_notes(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(1000, ge=1, le=1000),
    tag: str | None = None,
    source_path: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Note).options(defer(Note.content), selectinload(Note.tags).selectinload(NoteTag.tag))
    if tag:
        query = query.join(NoteTag).join(Tag).filter(Tag.name == tag.lower())
    if source_path:
        query = query.filter(Note.source_path == source_path)
    total = query.count()
    notes = query.order_by(Note.created_at.desc()).offset(skip).limit(limit).all()
    add_pagination_headers(response, total=total, limit=limit, offset=skip)
    return [note_to_response(n) for n in notes]


class SemanticSearchRequest(BaseModel):
    """Schema for semantic search queries (#353)."""

    query: str
    limit: int = 10
    threshold: float = 0.3  # max cosine distance to include a result


@router.post("/search/semantic")
async def semantic_search(
    req: SemanticSearchRequest,
    db: Session = Depends(get_db),
):
    """Semantic search over note embeddings using pgvector cosine similarity (#353).

    Embeds the query via the ai-service, then finds the top-K notes by
    cosine distance (``<=>``) from the stored embeddings.
    """
    if not settings.ai_service_enabled:
        raise HTTPException(status_code=503, detail="AI service is disabled")
    if not req.query.strip():
        return {"results": []}

    # 1. Embed the query via ai-service
    try:
        async with http_client(timeout=30.0) as client:
            headers = {}
            if settings.internal_secret:
                headers["X-Internal-Secret"] = settings.internal_secret
            resp = await client.post(
                f"{settings.ai_service_url}/embed",
                json={"note_id": 0, "content": req.query},
                headers=headers,
            )
            resp.raise_for_status()
            embedding = resp.json().get("embedding")
            if not embedding:
                return {"results": []}
    except Exception:
        raise HTTPException(status_code=503, detail="AI service unavailable for semantic search")

    # 2. Query pgvector for similar notes
    rows = db.execute(
        text("""
            SELECT ne.note_id, ne.embedding <=> :embedding AS distance
            FROM note_embeddings ne
            WHERE ne.embedding <=> :embedding <= :threshold
            ORDER BY ne.embedding <=> :embedding ASC
            LIMIT :limit
        """),
        {"embedding": str(embedding), "threshold": req.threshold, "limit": req.limit},
    ).fetchall()

    note_ids = [row[0] for row in rows]
    if not note_ids:
        return {"results": []}

    notes = (
        db.query(Note)
        .options(defer(Note.content), selectinload(Note.tags).selectinload(NoteTag.tag))
        .filter(Note.id.in_(note_ids))
        .all()
    )
    note_map = {n.id: n for n in notes}
    results = []
    for row in rows:
        note = note_map.get(row[0])
        if note:
            results.append(
                {
                    "note": note_to_response(note),
                    "score": 1.0 - float(row[1]),  # convert distance to similarity
                }
            )
    return {"results": results}


@router.get("/{note_id}")
def get_note(note_id: int, db: Session = Depends(get_db)):
    note = db.query(Note).options(selectinload(Note.tags).selectinload(NoteTag.tag)).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return note_to_response(note)


@router.post("/", status_code=201)
def create_note(
    request: Request,
    data: NoteCreate,
    background_tasks: BackgroundTasks,
    x_bulk_import: str | None = Header(default=None, alias="X-Bulk-Import"),
    x_from_vault: str | None = Header(default=None, alias="X-From-Vault"),
    db: Session = Depends(get_db),
):
    # Trust headers are honored only for the internal service token — a
    # regular client sending them gets the normal (stricter) write path.
    internal = _internal_service_request(request)
    from_vault = internal and _is_truthy_header(x_from_vault)
    bulk_import = internal and _is_truthy_header(x_bulk_import)
    # Internal-only provenance is clamped to "joidy" for regular clients.
    source = data.source if internal or data.source not in _INTERNAL_SOURCES else "joidy"
    _validated_source_path(
        db,
        data.source_path,
        note_id=None,
        writes_file=not from_vault,
    )
    note, gami = create_note_service(
        db,
        title=data.title,
        content=data.content,
        tags=data.tags,
        source=source,
        source_path=data.source_path,
        rebuild_derived_data=not bulk_import,
        from_vault=from_vault,
    )
    background_tasks.add_task(trigger_embedding, note.id, note.content)

    return {**note_to_response(note), "gamification": vars(gami)}


@router.put("/{note_id}")
def update_note(
    note_id: int,
    request: Request,
    data: NoteUpdate,
    background_tasks: BackgroundTasks,
    x_bulk_import: str | None = Header(default=None, alias="X-Bulk-Import"),
    x_from_vault: str | None = Header(default=None, alias="X-From-Vault"),
    db: Session = Depends(get_db),
):
    # Same internal-token gating as create_note (#1332).
    internal = _internal_service_request(request)
    from_vault = internal and _is_truthy_header(x_from_vault)
    bulk_import = internal and _is_truthy_header(x_bulk_import)
    source = data.source if internal or data.source not in _INTERNAL_SOURCES else "joidy"
    _validated_source_path(
        db,
        data.source_path,
        note_id=note_id,
        writes_file=not from_vault,
    )
    note, gami = update_note_service(
        db,
        note_id,
        title=data.title,
        content=data.content,
        tags=data.tags,
        source_path=data.source_path,
        source=source,
        rebuild_derived_data=not bulk_import,
        from_vault=from_vault,
    )
    if note is None or gami is None:
        raise HTTPException(status_code=404, detail="Note not found")
    background_tasks.add_task(trigger_embedding, note.id, note.content)

    return {**note_to_response(note), "gamification": vars(gami)}


@router.post("/rebuild-derived", status_code=202)
def rebuild_derived(db: Session = Depends(get_db)):
    rebuild_note_derived_data(db)
    return {"status": "ok"}


@router.post("/bulk-delete", status_code=200)
def bulk_delete(data: BulkIds, db: Session = Depends(get_db)):
    deleted = 0
    for nid in data.ids:
        if delete_note_service(db, nid):
            deleted += 1
    return {"deleted": deleted, "total": len(data.ids)}


@router.post("/bulk-tag", status_code=200)
def bulk_tag(data: BulkTagRequest, db: Session = Depends(get_db)):
    touched_tags: set[int] = set()
    added = 0
    for nid in data.ids:
        note = db.query(Note).filter(Note.id == nid).first()
        if not note:
            continue
        existing = {nt.tag_id for nt in note.tags}
        for tag_name in data.tags:
            tag = get_or_create_tag(db, tag_name)
            if tag.id not in existing:
                db.add(NoteTag(note_id=nid, tag_id=tag.id))
                touched_tags.add(tag.id)
                added += 1
    if touched_tags:
        sync_tag_cooccurrences_for_tags(db, touched_tags)
        sync_skills_for_tags(db, touched_tags)
    db.commit()
    return {"added": added, "notes": len(data.ids), "tags": data.tags}


@router.post("/bulk-untag", status_code=200)
def bulk_untag(data: BulkTagRequest, db: Session = Depends(get_db)):
    removed = 0
    touched_tags: set[int] = set()
    for nid in data.ids:
        for tag_name in data.tags:
            # data.tags is already sanitized/normalized by BulkTagRequest.validate_tags
            tag = db.query(Tag).filter(Tag.name == tag_name).first()
            if not tag:
                continue
            nt = db.query(NoteTag).filter(NoteTag.note_id == nid, NoteTag.tag_id == tag.id).first()
            if nt:
                db.delete(nt)
                touched_tags.add(tag.id)
                removed += 1
    if touched_tags:
        sync_tag_cooccurrences_for_tags(db, touched_tags)
        sync_skills_for_tags(db, touched_tags)
    db.commit()
    return {"removed": removed, "notes": len(data.ids), "tags": data.tags}


@router.delete("/by-path", status_code=200)
def delete_note_by_source_path(
    source_path: str = Query(..., max_length=1000),
    expected_updated_at: str | None = Query(default=None, max_length=64),
    db: Session = Depends(get_db),
):
    """Atomically delete the note whose ``source_path`` matches (#1302).

    The vault watcher used to list notes, capture an id, then delete it —
    a note re-created or updated between the list and the delete was
    removed anyway (TOCTOU). Here the match and the delete run inside one
    ``SELECT ... FOR UPDATE``-locked transaction, and
    ``expected_updated_at`` acts as an optimistic etag: when supplied and
    the row's ``updated_at`` differs (note changed or was recreated after
    the lookup), the delete is refused with 409 instead of silently
    removing the wrong note.

    Declared before ``DELETE /{note_id}``: without an int path converter,
    "by-path" would otherwise be swallowed by the ``{note_id}`` route and
    rejected as a 422.
    """
    normalized = normalize_source_path(source_path)
    if normalized is None or resolve_confined_source_path(normalized) is None:
        # Generic detail — distinguishing "outside vault" from "missing"
        # would leak a file-existence oracle (#1314).
        raise HTTPException(status_code=400, detail="Invalid source_path")

    note = db.query(Note).filter(Note.source_path == normalized).with_for_update().first()
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")

    if expected_updated_at:
        try:
            expected = datetime.fromisoformat(expected_updated_at.replace("Z", "+00:00"))
        except ValueError:
            expected = None
        if expected is not None and expected.tzinfo is not None:
            # note.updated_at is a naive UTC datetime; the API serializes
            # it as isoformat + "Z", so an aware etag is compared in UTC.
            expected = expected.astimezone(UTC).replace(tzinfo=None)
        if expected is None or expected != note.updated_at:
            raise HTTPException(status_code=409, detail="Note changed since lookup")

    note_id = note.id
    deleted = delete_note_service(db, note_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"deleted": note_id, "source_path": normalized}


@router.delete("/{note_id}", status_code=204)
def delete_note(note_id: int, db: Session = Depends(get_db)):
    deleted = delete_note_service(db, note_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Note not found")


@router.post("/{note_id}/accept-tag")
def accept_ai_tag(
    note_id: int,
    background_tasks: BackgroundTasks,
    tag_name: str = Query(max_length=MAX_TAG_LENGTH),
    db: Session = Depends(get_db),
):
    clean_tag = sanitize_tag(tag_name)
    if not clean_tag:
        raise HTTPException(status_code=422, detail="Tag name is empty after sanitization")
    tag, gami = accept_ai_tag_service(db, note_id, clean_tag)
    if tag is None or gami is None:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"tag": clean_tag, "gamification": vars(gami)}


@router.get("/{note_id}/backlinks")
def get_backlinks(note_id: int, db: Session = Depends(get_db)):
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    backlinks = list_backlinks_service(db, note_id)
    return [note_to_response(n) for n in backlinks]


@router.get("/{note_id}/similar")
def get_similar_notes(
    note_id: int,
    limit: int = Query(5, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Find semantically similar notes using pgvector cosine similarity (#393).

    Uses the note's stored embedding to find the top-K nearest neighbors.
    """
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    from models.note import NoteEmbedding

    embedding_row = db.query(NoteEmbedding).filter(NoteEmbedding.note_id == note_id).first()
    if not embedding_row or not embedding_row.embedding:
        return []

    rows = db.execute(
        text("""
            SELECT ne.note_id, ne.embedding <=> :embedding AS distance
            FROM note_embeddings ne
            WHERE ne.note_id != :note_id
            ORDER BY ne.embedding <=> :embedding ASC
            LIMIT :limit
        """),
        {"embedding": str(embedding_row.embedding), "note_id": note_id, "limit": limit},
    ).fetchall()

    note_ids = [row[0] for row in rows]
    if not note_ids:
        return []

    notes = (
        db.query(Note).options(selectinload(Note.tags).selectinload(NoteTag.tag)).filter(Note.id.in_(note_ids)).all()
    )
    note_map = {n.id: n for n in notes}
    results = []
    for row in rows:
        note = note_map.get(row[0])
        if note:
            results.append(
                {
                    "note": note_to_response(note),
                    "score": 1.0 - float(row[1]),
                }
            )
    return results


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
    entries = get_dead_letter_entries(db, limit=limit)
    note_ids = [e["note_id"] for e in entries]
    notes = (
        {n.id: n.title for n in db.query(Note.id, Note.title).filter(Note.id.in_(note_ids)).all()} if note_ids else {}
    )
    for e in entries:
        e["note_title"] = notes.get(e["note_id"])
    return entries


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
