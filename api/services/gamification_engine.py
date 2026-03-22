"""
Gamification Engine — the heart of Joidy's dopamine loop.

Every mutation in the system calls process_event(), which:
1. Awards XP
2. Updates the streak
3. Recalculates the plant stage
4. Returns a GamificationResult for the frontend to animate
"""

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from models.gamification import StreakRecord, UserStats, XPEvent

XP_TABLE = {
    "note_created": 10,
    "note_edited": 5,
    "tag_added": 3,
    "tag_accepted_ai": 4,
    "topic_connected": 8,
    "goal_completed": 50,
    "daily_activity": 15,
    "streak_milestone_7": 100,
    "streak_milestone_30": 100,
    "streak_milestone_100": 100,
    "note_imported_obsidian": 2,
}

PLANT_STAGES = [
    (0, "seed"),
    (100, "sprout"),
    (500, "seedling"),
    (1500, "young"),
    (4000, "mature"),
    (10000, "flowering"),
    (25000, "tree"),
]

STREAK_MILESTONES = {7, 30, 100, 365}
GRACE_PERIOD_DAYS = 1  # One missed day forgiven per week


@dataclass
class GamificationResult:
    xp_awarded: int = 0
    total_xp: int = 0
    current_streak: int = 0
    plant_stage: int = 0
    plant_stage_name: str = "seed"
    plant_stage_changed: bool = False
    streak_changed: bool = False
    milestone_reached: int | None = None
    new_skill_unlocked: str | None = None
    message: str = ""


def _get_or_create_stats(db: Session) -> UserStats:
    stats = db.query(UserStats).filter(UserStats.id == 1).first()
    if not stats:
        stats = UserStats(id=1)
        db.add(stats)
        db.flush()
    return stats


def _compute_plant_stage(total_xp: int) -> tuple[int, str]:
    stage_idx = 0
    for i, (threshold, name) in enumerate(PLANT_STAGES):
        if total_xp >= threshold:
            stage_idx = i
    return stage_idx, PLANT_STAGES[stage_idx][1]


def _compute_streak(db: Session, stats: UserStats) -> tuple[int, bool]:
    today = date.today()
    last = stats.last_activity_date

    if last is None or last == today:
        return stats.current_streak, False

    days_since = (today - last).days
    if days_since == 1:
        # Consecutive day — streak continues
        new_streak = stats.current_streak + 1
    elif days_since <= GRACE_PERIOD_DAYS + 1:
        # Grace period — don't break streak, but don't increment
        new_streak = stats.current_streak
    else:
        # Streak broken
        new_streak = 1

    return new_streak, new_streak != stats.current_streak


def process_event(
    db: Session,
    event_type: str,
    metadata: dict | None = None,
) -> GamificationResult:
    xp = XP_TABLE.get(event_type, 0)
    if metadata is None:
        metadata = {}

    # Record XP event
    event = XPEvent(event_type=event_type, xp=xp, metadata_json=json.dumps(metadata))
    db.add(event)

    stats = _get_or_create_stats(db)
    old_plant_stage = stats.plant_stage
    today = date.today()

    # Add XP
    stats.total_xp += xp

    # Update streak
    new_streak, streak_changed = _compute_streak(db, stats)
    is_new_day = stats.last_activity_date != today

    if is_new_day:
        stats.current_streak = new_streak
        stats.last_activity_date = today
        # Record activity for this day
        existing = db.query(StreakRecord).filter(StreakRecord.activity_date == today).first()
        if not existing:
            db.add(StreakRecord(activity_date=today, xp_earned=xp))
            # Award daily activity bonus only if not already the daily_activity event
            if event_type != "daily_activity":
                daily_xp = XP_TABLE["daily_activity"]
                stats.total_xp += daily_xp
                xp += daily_xp
                db.add(XPEvent(event_type="daily_activity", xp=daily_xp))
        if new_streak > stats.longest_streak:
            stats.longest_streak = new_streak
    else:
        existing_streak_record = db.query(StreakRecord).filter(
            StreakRecord.activity_date == today
        ).first()
        if existing_streak_record:
            existing_streak_record.xp_earned += xp

    # Check streak milestones
    milestone_reached = None
    if is_new_day and new_streak in STREAK_MILESTONES:
        milestone_xp = XP_TABLE.get(f"streak_milestone_{new_streak}", 100)
        stats.total_xp += milestone_xp
        xp += milestone_xp
        db.add(XPEvent(event_type=f"streak_milestone_{new_streak}", xp=milestone_xp))
        milestone_reached = new_streak

    # Update plant stage
    new_stage, new_stage_name = _compute_plant_stage(stats.total_xp)
    stats.plant_stage = new_stage
    plant_stage_changed = new_stage != old_plant_stage

    db.commit()
    db.refresh(stats)

    return GamificationResult(
        xp_awarded=xp,
        total_xp=stats.total_xp,
        current_streak=stats.current_streak,
        plant_stage=new_stage,
        plant_stage_name=new_stage_name,
        plant_stage_changed=plant_stage_changed,
        streak_changed=streak_changed,
        milestone_reached=milestone_reached,
        message=_build_message(event_type, xp, new_stage_name, milestone_reached, plant_stage_changed),
    )


def _build_message(
    event_type: str, xp: int, stage_name: str, milestone: int | None, stage_changed: bool
) -> str:
    parts = [f"+{xp} XP"]
    if stage_changed:
        parts.append(f"Tu planta creció: {stage_name}!")
    if milestone:
        parts.append(f"{milestone} días de racha!")
    return " · ".join(parts)
