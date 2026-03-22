"""
Skill Tree Service — derives the RPG skill tree from note/tag data.
Skills are auto-generated from tags, no manual configuration needed.
"""

from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from models.note import NoteTag, Tag
from models.skill import Skill, compute_skill_level


def sync_skills(db: Session) -> list[dict]:
    """Recalculate all skills based on current note counts per tag."""
    tag_counts = (
        db.query(NoteTag.tag_id, func.count(NoteTag.note_id).label("count"))
        .group_by(NoteTag.tag_id)
        .all()
    )

    updated = []
    for tag_id, count in tag_counts:
        skill = db.query(Skill).filter(Skill.tag_id == tag_id).first()
        new_level = compute_skill_level(count)

        if not skill:
            skill = Skill(tag_id=tag_id, note_count=count, level=new_level)
            if new_level != "locked":
                skill.first_unlocked_at = datetime.utcnow()
            db.add(skill)
            updated.append({"tag_id": tag_id, "level": new_level, "new": True})
        else:
            prev_level = skill.level
            skill.note_count = count
            skill.level = new_level
            if prev_level == "locked" and new_level != "locked":
                skill.first_unlocked_at = datetime.utcnow()
                updated.append({"tag_id": tag_id, "level": new_level, "new": True, "unlocked": True})
            else:
                updated.append({"tag_id": tag_id, "level": new_level, "new": False})

    db.commit()
    return updated


def get_skill_tree(db: Session) -> dict:
    """Return skill tree as nested structure for D3 visualization."""
    skills = db.query(Skill).all()
    tags = {t.id: t for t in db.query(Tag).all()}

    nodes = []
    edges = []

    for skill in skills:
        tag = tags.get(skill.tag_id)
        if not tag:
            continue
        nodes.append({
            "id": skill.tag_id,
            "name": tag.name,
            "level": skill.level,
            "note_count": skill.note_count,
            "xp": skill.xp,
        })
        if tag.parent_id and tag.parent_id in tags:
            edges.append({"source": tag.parent_id, "target": skill.tag_id})

    return {"nodes": nodes, "edges": edges}
