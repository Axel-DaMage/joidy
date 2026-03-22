"""
Joidy Vault Writer — writes Joidy-owned files into _joidy/ inside the Obsidian vault.
Joidy NEVER modifies files outside of _joidy/.
"""

import os
from datetime import date, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from models.gamification import StreakRecord, UserStats
from models.goal import Goal
from models.note import NoteTag, Tag
from models.skill import Skill


JOIDY_DIR = "_joidy"
JOIDY_HEADER = "joidy_managed: true"


def get_vault_path() -> Path | None:
    vault = os.environ.get("VAULT_PATH", "")
    if not vault:
        return None
    p = Path(vault)
    return p if p.exists() else None


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
    vault = get_vault_path()
    if not vault:
        return False

    joidy_dir = vault / JOIDY_DIR
    joidy_dir.mkdir(parents=True, exist_ok=True)
    filepath = joidy_dir / "objectives.md"

    active_goals = db.query(Goal).filter(Goal.is_completed == False).all()
    completed_goals = db.query(Goal).filter(Goal.is_completed == True).order_by(Goal.completed_at.desc()).limit(10).all()

    now = datetime.utcnow().isoformat()
    content = f"""---
{JOIDY_HEADER}
last_sync: {now}
---

# Objetivos Joidy

## En progreso
{_format_goals(active_goals, db, checked=False)}

## Completados (últimos 10)
{_format_goals(completed_goals, db, checked=True)}
"""

    filepath.write_text(content, encoding="utf-8")
    return True


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

    content = f"""---
{JOIDY_HEADER}
---

# Árbol de Habilidades

{'chr(10).join(lines) if lines else 'Sin habilidades aún. Crea notas y agrega tags para comenzar.'}
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
    from models.note import Note
    from datetime import datetime
    start = datetime.combine(today, datetime.min.time())
    end = datetime.combine(today, datetime.max.time())
    return db.query(Note).filter(Note.created_at >= start, Note.created_at <= end).all()


def _get_top_tags_week(db: Session) -> list:
    from datetime import timedelta
    from models.note import Note, NoteTag, Tag
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
