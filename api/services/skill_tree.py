"""
Skill Tree Service — derives the RPG skill tree from note/tag data.
Skills are auto-generated from tags, no manual configuration needed.
"""

from datetime import datetime, timezone

from models.note import NoteTag, Tag
from models.skill import Skill, compute_skill_level
from repositories import SkillRepository
from sqlalchemy import func
from sqlalchemy.orm import Session


def sync_skills_for_tags(db: Session, tag_ids: set[int]) -> list[dict]:
    """Recalculate skills only for the provided tag ids."""
    if not tag_ids:
        return []

    tag_counts = dict(
        db.query(NoteTag.tag_id, func.count(NoteTag.note_id).label("count"))
        .filter(NoteTag.tag_id.in_(tag_ids))
        .group_by(NoteTag.tag_id)
        .all()
    )
    skills_by_tag = {skill.tag_id: skill for skill in SkillRepository(db)._db.query(Skill).filter(Skill.tag_id.in_(tag_ids)).all()}

    updated = []
    for tag_id in tag_ids:
        count = tag_counts.get(tag_id, 0)
        skill = skills_by_tag.get(tag_id)
        new_level = compute_skill_level(count)

        if skill is None:
            if count <= 0:
                continue
            skill = Skill(tag_id=tag_id, note_count=count, level=new_level)
            if new_level != "locked":
                skill.first_unlocked_at = datetime.now(timezone.utc)
            db.add(skill)
            updated.append({"tag_id": tag_id, "level": new_level, "new": True})
            continue

        prev_count = skill.note_count
        prev_level = skill.level
        if prev_count == count and prev_level == new_level:
            continue

        skill.note_count = count
        skill.level = new_level

        if prev_level == "locked" and new_level != "locked":
            skill.first_unlocked_at = datetime.now(timezone.utc)
            updated.append({"tag_id": tag_id, "level": new_level, "new": False, "unlocked": True})
        else:
            updated.append({"tag_id": tag_id, "level": new_level, "new": False})

    db.commit()
    return updated


def sync_skills(db: Session) -> list[dict]:
    """Recalculate all skills based on current note counts per tag."""
    tag_counts = dict(
        db.query(NoteTag.tag_id, func.count(NoteTag.note_id).label("count"))
        .group_by(NoteTag.tag_id)
        .all()
    )
    skills_by_tag = {skill.tag_id: skill for skill in SkillRepository(db).list()}

    updated = []
    for tag_id, skill in skills_by_tag.items():
        count = tag_counts.pop(tag_id, 0)
        new_level = compute_skill_level(count)
        prev_count = skill.note_count
        prev_level = skill.level

        if prev_count == count and prev_level == new_level:
            continue

        skill.note_count = count
        skill.level = new_level

        if prev_level == "locked" and new_level != "locked":
            skill.first_unlocked_at = datetime.now(timezone.utc)
            updated.append({"tag_id": tag_id, "level": new_level, "new": False, "unlocked": True})
        else:
            updated.append({"tag_id": tag_id, "level": new_level, "new": False})

    for tag_id, count in tag_counts.items():
        if count <= 0:
            continue
        new_level = compute_skill_level(count)
        skill = Skill(tag_id=tag_id, note_count=count, level=new_level)
        if new_level != "locked":
            skill.first_unlocked_at = datetime.now(timezone.utc)
        db.add(skill)
        updated.append({"tag_id": tag_id, "level": new_level, "new": True})

    db.commit()
    return updated


def get_skill_tree(db: Session) -> dict:
    """Return skill tree as nested structure for D3 visualization."""
    skills = SkillRepository(db).list()
    if not skills:
        return {"nodes": [], "edges": []}

    # Fetch only the tags referenced by skills (and their parent tags) instead
    # of TagRepository(db).list(), which caps at 100 rows. When a user has
    # 100+ tags from notes, skill tags with IDs > 100 were missing from the
    # dict and the corresponding nodes were silently skipped, so the tree
    # rendered fewer nodes than the sidebar (#206).
    tag_ids = {s.tag_id for s in skills}
    tags = {t.id: t for t in db.query(Tag).filter(Tag.id.in_(tag_ids)).all()}
    # Include parent tags so edges can be drawn.
    parent_ids = {t.parent_id for t in tags.values() if t.parent_id}
    if parent_ids:
        tags.update({t.id: t for t in db.query(Tag).filter(Tag.id.in_(parent_ids)).all()})

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
