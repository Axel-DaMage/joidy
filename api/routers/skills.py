from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models.note import Tag
from models.skill import Skill
from services.skill_tree import get_skill_tree, sync_skills

router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("/")
def list_skills(db: Session = Depends(get_db)):
    skills = db.query(Skill).filter(Skill.level != "locked").order_by(Skill.note_count.desc()).all()
    tags = {t.id: t for t in db.query(Tag).all()}
    return [
        {
            "id": s.id,
            "tag_id": s.tag_id,
            "tag_name": tags[s.tag_id].name if s.tag_id in tags else "unknown",
            "level": s.level,
            "note_count": s.note_count,
            "first_unlocked_at": s.first_unlocked_at.isoformat() if s.first_unlocked_at else None,
        }
        for s in skills
    ]


@router.get("/tree")
def skill_tree(db: Session = Depends(get_db)):
    return get_skill_tree(db)


@router.post("/sync")
def sync(db: Session = Depends(get_db)):
    updated = sync_skills(db)
    return {"synced": len(updated), "updates": updated}
