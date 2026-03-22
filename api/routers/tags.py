from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.note import NoteTag, Tag

router = APIRouter(prefix="/tags", tags=["tags"])


class TagCreate(BaseModel):
    name: str
    parent_id: Optional[int] = None


@router.get("/")
def list_tags(db: Session = Depends(get_db)):
    tags = db.query(Tag).order_by(Tag.name).all()
    return [
        {
            "id": t.id,
            "name": t.name,
            "parent_id": t.parent_id,
            "note_count": db.query(NoteTag).filter(NoteTag.tag_id == t.id).count(),
        }
        for t in tags
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
    return {"id": tag.id, "name": tag.name, "parent_id": tag.parent_id}


@router.put("/{tag_id}/parent")
def set_parent(tag_id: int, parent_id: Optional[int], db: Session = Depends(get_db)):
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    tag.parent_id = parent_id
    db.commit()
    return {"id": tag.id, "name": tag.name, "parent_id": tag.parent_id}


@router.get("/graph")
def get_tag_graph(db: Session = Depends(get_db)):
    """Returns nodes + edges for the knowledge graph."""
    tags = db.query(Tag).all()
    nodes = []
    edges = []

    for tag in tags:
        count = db.query(NoteTag).filter(NoteTag.tag_id == tag.id).count()
        nodes.append({
            "id": tag.id,
            "name": tag.name,
            "note_count": count,
            "parent_id": tag.parent_id,
        })
        if tag.parent_id:
            edges.append({"source": tag.parent_id, "target": tag.id, "type": "hierarchy"})

    # Co-occurrence edges
    tag_ids = [t.id for t in tags]
    for i, t1 in enumerate(tag_ids):
        for t2 in tag_ids[i + 1:]:
            shared = (
                db.query(NoteTag.note_id)
                .filter(NoteTag.tag_id == t1)
                .intersect(db.query(NoteTag.note_id).filter(NoteTag.tag_id == t2))
                .count()
            )
            if shared >= 2:
                edges.append({"source": t1, "target": t2, "type": "cooccurrence", "weight": shared})

    return {"nodes": nodes, "edges": edges}
