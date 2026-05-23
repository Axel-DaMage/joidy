from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from models.note import Note, NoteTag, Tag, TagCooccurrence, NoteLink
from services.response_cache import clear_api_caches, register_cache_clearer, ttl_cache

router = APIRouter(prefix="/tags", tags=["tags"])


class TagCreate(BaseModel):
    name: str
    parent_id: Optional[int] = None


@ttl_cache(ignore_params={"db"})
def _tags_with_note_counts(db: Session):
    return (
        db.query(Tag, func.count(NoteTag.tag_id).label("note_count"))
        .outerjoin(NoteTag, NoteTag.tag_id == Tag.id)
        .group_by(Tag.id)
        .order_by(Tag.name)
        .all()
    )


register_cache_clearer(_tags_with_note_counts.cache_clear)  # type: ignore[attr-defined]


@router.get("/")
def list_tags(db: Session = Depends(get_db)):
    return [
        {
            "id": tag.id,
            "name": tag.name,
            "parent_id": tag.parent_id,
            "note_count": note_count,
        }
        for tag, note_count in _tags_with_note_counts(db)
    ]


@router.post("/", status_code=201)
def create_tag(data: TagCreate, db: Session = Depends(get_db)):
    existing = db.query(Tag).filter(Tag.name == data.name.lower().strip()).first()
    if existing:
        raise HTTPException(status_code=409, detail="Tag already exists")
    tag = Tag(name=data.name.lower().strip(), parent_id=data.parent_id)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    clear_api_caches()
    return {"id": tag.id, "name": tag.name, "parent_id": tag.parent_id}


@router.put("/{tag_id}/parent")
def set_parent(tag_id: int, parent_id: Optional[int], db: Session = Depends(get_db)):
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    # Prevent self-referencing
    if parent_id == tag_id:
        raise HTTPException(status_code=400, detail="A tag cannot be its own parent")

    # Detect cycles: walk up the parent chain from parent_id
    if parent_id is not None:
        visited = {tag_id}
        current = parent_id
        while current is not None:
            if current in visited:
                raise HTTPException(
                    status_code=400,
                    detail="Setting this parent would create a circular hierarchy"
                )
            visited.add(current)
            parent_tag = db.query(Tag).filter(Tag.id == current).first()
            current = parent_tag.parent_id if parent_tag else None

    tag.parent_id = parent_id
    db.commit()
    clear_api_caches()
    return {"id": tag.id, "name": tag.name, "parent_id": tag.parent_id}


@ttl_cache(ignore_params={"db"})
def _cached_tag_graph(db: Session):
    """Returns nodes + edges for the knowledge graph (tags + notes)."""
    nodes = []
    edges = []

    # Tags as nodes (negative IDs to distinguish from notes)
    tag_node_offset = 1
    for tag, note_count in _tags_with_note_counts(db):
        nodes.append({
            "id": tag.id,
            "type": "tag",
            "name": tag.name,
            "note_count": note_count,
            "parent_id": tag.parent_id,
            "group": "tag",
        })
        if tag.parent_id:
            edges.append({"source": tag.parent_id, "target": tag.id, "type": "hierarchy", "weight": 1})

    # Notes as nodes (positive IDs)
    notes = db.query(Note).filter(Note.is_embedded == False).all()
    note_links = db.query(NoteLink).all()
    note_tag_relations = db.query(NoteTag).all()

    for note in notes:
        nodes.append({
            "id": note.id,
            "type": "note",
            "title": note.title,
            "path": note.source_path,
            "group": "note",
        })

    # Note-to-note links (wikilinks)
    for link in note_links:
        edges.append({
            "source": link.source_note_id,
            "target": link.target_note_id,
            "type": "linked",
            "weight": 1,
        })

    # Note-to-tag relations (tagged)
    for nt in note_tag_relations:
        edges.append({
            "source": nt.note_id,
            "target": nt.tag_id,
            "type": "tagged",
            "weight": 1,
        })

    # Tag cooccurrences
    cooccurrence_edges = db.query(TagCooccurrence).all()
    for edge in cooccurrence_edges:
        edges.append({
            "source": edge.tag_a_id,
            "target": edge.tag_b_id,
            "type": "cooccurrence",
            "weight": edge.weight,
        })

    return {"nodes": nodes, "edges": edges}


register_cache_clearer(_cached_tag_graph.cache_clear)  # type: ignore[attr-defined]


@router.get("/graph")
def get_tag_graph(db: Session = Depends(get_db)):
    return _cached_tag_graph(db)
