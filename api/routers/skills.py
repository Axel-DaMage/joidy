from database import get_db
from fastapi import APIRouter, Depends
from models.note import Tag
from models.skill import Skill
from services.response_cache import clear_api_caches, register_cache_clearer, ttl_cache
from services.skill_tree import get_skill_tree, sync_skills
from sqlalchemy.orm import Session

router = APIRouter(prefix="/skills", tags=["skills"])


@ttl_cache(ignore_params={"db"})
def _cached_list_skills(db: Session):
    skills = db.query(Skill).filter(Skill.level != "locked").order_by(Skill.note_count.desc()).all()
    tag_rows = db.query(Tag.id, Tag.name).all()
    tags = {tag_id: tag_name for tag_id, tag_name in tag_rows}
    return [
        {
            "id": s.id,
            "tag_id": s.tag_id,
            "tag_name": tags.get(s.tag_id, "unknown"),
            "level": s.level,
            "note_count": s.note_count,
            "first_unlocked_at": s.first_unlocked_at.isoformat() if s.first_unlocked_at else None,
        }
        for s in skills
    ]


register_cache_clearer(_cached_list_skills.cache_clear)  # type: ignore[attr-defined]


def list_skills(db: Session = Depends(get_db)):
    return _cached_list_skills(db)


@ttl_cache(ignore_params={"db"})
def _cached_skill_tree(db: Session):
    return get_skill_tree(db)


register_cache_clearer(_cached_skill_tree.cache_clear)  # type: ignore[attr-defined]


@router.get("/tree")
def skill_tree(db: Session = Depends(get_db)):
    return _cached_skill_tree(db)


@router.post("/sync")
def sync(db: Session = Depends(get_db)):
    updated = sync_skills(db)
    clear_api_caches()
    return {"synced": len(updated), "updates": updated}
