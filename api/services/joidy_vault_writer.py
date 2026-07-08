"""
Joidy Vault Writer — writes Joidy-owned files into _joidy/ inside the Obsidian vault.
Joidy NEVER modifies files outside of _joidy/.
"""

import os
from datetime import date, datetime
from pathlib import Path

from models.gamification import StreakRecord, UserStats
from models.goal import Goal
from models.note import NoteTag, Tag
from models.skill import Skill
from sqlalchemy.orm import Session

JOIDY_DIR = "_joidy"
JOIDY_HEADER = "joidy_managed: true"
OBJECTIVES_DIR = "Objetivos"


def get_vault_path() -> Path | None:
    vault = os.environ.get("VAULT_PATH", "")
    if not vault:
        return None
    p = Path(vault)
    return p if p.exists() else None


def get_objectives_dir() -> Path | None:
    vault = get_vault_path()
    if not vault:
        return None
    obj_dir = vault / OBJECTIVES_DIR
    obj_dir.mkdir(parents=True, exist_ok=True)
    return obj_dir


def read_goal_file(goal_id: int) -> dict | None:
    obj_dir = get_objectives_dir()
    if not obj_dir:
        return None
    for f in obj_dir.glob(f"{goal_id}_*.md"):
        content = f.read_text(encoding="utf-8")
        return _parse_goal_content(content)
    return None


def _parse_goal_content(content: str) -> dict:
    lines = content.split("\n")
    frontmatter = {}
    body_lines = []
    in_frontmatter = False

    for line in lines:
        if line.strip() == "---":
            if not in_frontmatter:
                in_frontmatter = True
                continue
            else:
                in_frontmatter = False
                continue
        if in_frontmatter:
            if ":" in line:
                key, _, val = line.partition(":")
                frontmatter[key.strip()] = val.strip()
        else:
            body_lines.append(line)

    title = ""
    if body_lines:
        first = body_lines[0].strip()
        if first.startswith("# "):
            title = first[1:].strip()

    body = "\n".join(body_lines[1:]).strip()

    return {
        "title": frontmatter.get("title", title),
        "content": body,
        **frontmatter,
    }


def update_goal_file(goal_id: int, title: str, content: str, metadata: dict) -> bool:
    obj_dir = get_objectives_dir()
    if not obj_dir:
        return False

    filepath = None
    for f in obj_dir.glob(f"{goal_id}_*.md"):
        filepath = f
        break

    if not filepath:
        s = slugify(title)
        filepath = obj_dir / f"{goal_id}_{s}.md"

    meta = {k: v for k, v in metadata.items() if v is not None}
    meta["goal_id"] = goal_id
    meta["joidy_managed"] = True

    content_lines = ["---"]
    for k, v in meta.items():
        content_lines.append(f"{k}: {v}")
    content_lines.append("---\n")
    content_lines.append(f"# {title}\n")
    if content:
        content_lines.append(f"\n{content}\n")

    filepath.write_text("\n".join(content_lines), encoding="utf-8")
    return True


def delete_goal_file(goal_id: int) -> bool:
    obj_dir = get_objectives_dir()
    if not obj_dir:
        return False

    for f in obj_dir.glob(f"{goal_id}_*.md"):
        f.unlink()
        return True
    return False


def write_daily(db: Session, target_date: date | None = None) -> bool:
    vault = get_vault_path()
    if not vault:
        return False

    today = target_date or date.today()
    daily_dir = vault / JOIDY_DIR / "daily"
    daily_dir.mkdir(parents=True, exist_ok=True)
    filepath = daily_dir / f"{today.isoformat()}.md"

    stats = db.query(UserStats).filter(UserStats.id == 1).first()
    streak_record = db.query(StreakRecord).filter(StreakRecord.activity_date == today).first()
    xp_today = streak_record.xp_earned if streak_record else 0

    notes_today = _get_notes_created_today(db, today)
    top_tags = _get_top_tags_week(db)

    content = f"""---
{JOIDY_HEADER}
date: {today.isoformat()}
xp_earned: {xp_today}
streak_day: {stats.current_streak if stats else 0}
---

# Daily Journal — {today.strftime("%B %d, %Y")}

## Actividad de hoy
- XP ganado: **{xp_today}**
- Racha: **{stats.current_streak if stats else 0} días**
- XP total: **{stats.total_xp if stats else 0}**

## Notas creadas hoy
{_format_note_list(notes_today)}

## Tags más activos esta semana
{_format_tag_list(top_tags)}
"""

    filepath.write_text(content, encoding="utf-8")
    return True


def write_objectives(db: Session) -> bool:
    obj_dir = get_objectives_dir()
    if not obj_dir:
        return False

    goals = db.query(Goal).order_by(Goal.created_at.desc()).all()
    for goal in goals:
        _write_goal_file(db, goal, obj_dir)
    return True


def _write_goal_file(db: Session, goal: Goal, obj_dir: Path) -> Path | None:
    s = slugify(goal.title)
    filepath = obj_dir / f"{goal.id}_{s}.md"

    frontmatter = {
        "goal_id": goal.id,
        "joidy_managed": True,
        "temporality": goal.temporality,
        "measurement_type": goal.measurement_type,
        "target_value": goal.target_value,
        "current_value": goal.current_value,
        "state": goal.state,
        "fail_config": goal.fail_config,
        "fail_emoji": goal.fail_emoji,
        "color": goal.color,
        "theme": goal.theme,
        "note_id": goal.note_id,
        "tag_id": goal.tag_id,
        "parent_id": goal.parent_id,
        "max_assignment_days": goal.max_assignment_days,
        "is_completed": goal.is_completed,
        "completed_at": goal.completed_at.isoformat() if goal.completed_at else None,
    }

    content_lines = ["---"]
    for k, v in frontmatter.items():
        if v is not None:
            content_lines.append(f"{k}: {v}")
    content_lines.append("---\n")

    content_lines.append(f"# {goal.title}\n")
    if goal.description:
        content_lines.append(f"\n{goal.description}\n")

    filepath.write_text("\n".join(content_lines), encoding="utf-8")

    goal.source_path = str(filepath.relative_to(filepath.parents[1]))
    return filepath


def slugify(text: str) -> str:
    import re
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def write_skills(db: Session) -> bool:
    vault = get_vault_path()
    if not vault:
        return False

    joidy_dir = vault / JOIDY_DIR
    joidy_dir.mkdir(parents=True, exist_ok=True)
    filepath = joidy_dir / "skills.md"

    skills = db.query(Skill).filter(Skill.level != "locked").order_by(Skill.note_count.desc()).all()
    tags = {t.id: t for t in db.query(Tag).all()}

    # Build tree
    lines = []
    root_skills = [s for s in skills if tags.get(s.tag_id) and tags[s.tag_id].parent_id is None]
    for skill in root_skills:
        tag = tags[skill.tag_id]
        lines.append(f"## {tag.name} ({_level_display(skill.level)} — {skill.note_count} notas)")
        _write_skill_children(skill.tag_id, skills, tags, lines, indent=1)

    skills_text = "\n".join(lines) if lines else "Sin habilidades aún. Crea notas y agrega tags para comenzar."
    content = f"""---
{JOIDY_HEADER}
---

# Árbol de Habilidades

{skills_text}
"""

    filepath.write_text(content, encoding="utf-8")
    return True


def write_readme(vault_path: Path) -> None:
    """Write the warning note in _joidy/ for Obsidian users."""
    joidy_dir = vault_path / JOIDY_DIR
    joidy_dir.mkdir(parents=True, exist_ok=True)
    readme = joidy_dir / "README.md"
    if not readme.exists():
        readme.write_text(
            "# ⚠️ Carpeta administrada por Joidy\n\n"
            "No edites estos archivos manualmente — Joidy los sobreescribirá.\n\n"
            "Puedes **leer** estos archivos y enlazarlos desde tus notas con:\n"
            "- `[[_joidy/objectives]]`\n"
            "- `[[_joidy/skills]]`\n"
            "- `[[_joidy/daily/2026-03-22]]`\n",
            encoding="utf-8",
        )


def _get_notes_created_today(db: Session, today: date) -> list:
    from datetime import datetime

    from models.note import Note
    start = datetime.combine(today, datetime.min.time())
    end = datetime.combine(today, datetime.max.time())
    return db.query(Note).filter(Note.created_at >= start, Note.created_at <= end).all()


def _get_top_tags_week(db: Session) -> list:
    from datetime import timedelta

    from models.note import Note, Tag
    week_ago = datetime.utcnow() - timedelta(days=7)
    results = (
        db.query(Tag.name, Tag.id)
        .join(NoteTag, NoteTag.tag_id == Tag.id)
        .join(Note, Note.id == NoteTag.note_id)
        .filter(Note.updated_at >= week_ago)
        .group_by(Tag.id)
        .limit(5)
        .all()
    )
    return results


def _format_note_list(notes) -> str:
    if not notes:
        return "- (ninguna nota creada hoy)"
    return "\n".join(f"- {n.title}" for n in notes)


def _format_tag_list(tags) -> str:
    if not tags:
        return "- (sin actividad esta semana)"
    return "\n".join(f"- {name}" for name, _ in tags)


def _format_goals(goals, db, checked: bool) -> str:
    if not goals:
        return "- (ninguno)"
    check = "x" if checked else " "
    lines = []
    for g in goals:
        progress = _goal_progress(g, db)
        lines.append(f"- [{check}] {g.title}{progress}")
    return "\n".join(lines)


def _goal_progress(goal: Goal, db: Session) -> str:
    if goal.tag_id:
        from models.note import NoteTag
        count = db.query(NoteTag).filter(NoteTag.tag_id == goal.tag_id).count()
        return f" ({count}/{goal.target_notes} notas)"
    return ""


def _write_skill_children(parent_id: int, skills, tags, lines, indent: int) -> None:
    children = [s for s in skills if tags.get(s.tag_id) and tags[s.tag_id].parent_id == parent_id]
    prefix = "  " * indent + "↳ "
    for skill in children:
        tag = tags[skill.tag_id]
        lines.append(f"{prefix}{tag.name} ({_level_display(skill.level)} — {skill.note_count} notas)")
        _write_skill_children(skill.tag_id, skills, tags, lines, indent + 1)


def _level_display(level: str) -> str:
    levels = {"apprentice": "Aprendiz", "journeyman": "Oficial", "expert": "Experto", "master": "Maestro"}
    return levels.get(level, level.title())
