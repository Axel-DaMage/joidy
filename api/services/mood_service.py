"""Mood Tracker Service — daily mood recording and analytics."""

from datetime import date, timedelta

from models.mood_entry import MoodEntry
from services.timezone_utils import get_local_today
from sqlalchemy import case, func
from sqlalchemy.orm import Session


def _today() -> date:
    return get_local_today()


def create_or_update_mood(db: Session, user_id: int, score: int, note: str | None = None) -> MoodEntry:
    """Create or update today's mood entry for a user (upsert by date)."""
    today = _today()
    entry = db.query(MoodEntry).filter(MoodEntry.user_id == user_id, MoodEntry.entry_date == today).first()
    if entry:
        entry.score = score
        entry.note = note
    else:
        entry = MoodEntry(
            user_id=user_id,
            score=score,
            note=note,
            entry_date=today,
        )
        db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_today_mood(db: Session, user_id: int) -> MoodEntry | None:
    """Get today's mood entry for a user, or None if not yet recorded."""
    return db.query(MoodEntry).filter(MoodEntry.user_id == user_id, MoodEntry.entry_date == _today()).first()


def get_mood_history(db: Session, user_id: int, days: int = 30) -> list[MoodEntry]:
    """Get mood entries for the last N days, ordered oldest → newest."""
    if days < 1:
        days = 1
    if days > 366:
        days = 366
    since = _today() - timedelta(days=days)
    return (
        db.query(MoodEntry)
        .filter(
            MoodEntry.user_id == user_id,
            MoodEntry.entry_date >= since,
        )
        .order_by(MoodEntry.entry_date.asc())
        .all()
    )


def get_mood_stats(db: Session, user_id: int) -> dict:
    """Compute mood statistics: average score, current streak, and note correlation.

    - ``average``: mean score across all entries (rounded to 2 decimals).
    - ``streak``: consecutive days (ending today or yesterday) with a mood entry.
    - ``total_entries``: total number of recorded mood entries.
    - ``notes_correlation``: how many mood entries include a note vs. total.
    """
    # Aggregate in SQL instead of hydrating every entry ever recorded (#1523):
    # one row for count/avg/notes stats, plus a single-column projection of
    # entry_date for the consecutive-day streak walk.
    agg = (
        db.query(
            func.count(MoodEntry.id).label("total"),
            func.avg(MoodEntry.score).label("avg_score"),
            func.coalesce(
                func.sum(case((func.trim(MoodEntry.note) != "", 1), else_=0)),
                0,
            ).label("with_note"),
        )
        .filter(MoodEntry.user_id == user_id)
        .one()
    )
    total = int(agg.total)

    if total == 0:
        return {
            "average": 0.0,
            "streak": 0,
            "total_entries": 0,
            "notes_correlation": 0.0,
        }

    # Average score (rounded in Python to keep half-even semantics identical
    # across PostgreSQL/SQLite backends)
    avg = round(float(agg.avg_score), 2)

    # Current streak — consecutive days ending today or yesterday
    dates_set = {
        row[0]
        for row in db.query(MoodEntry.entry_date)
        .filter(MoodEntry.user_id == user_id)
        .order_by(MoodEntry.entry_date.asc())
        .all()
    }
    today = _today()
    cursor = today
    if cursor not in dates_set:
        cursor -= timedelta(days=1)
    streak = 0
    while cursor in dates_set:
        streak += 1
        cursor -= timedelta(days=1)

    # Correlation: fraction of entries that include a non-blank note
    notes_correlation = round(int(agg.with_note) / total, 2)

    return {
        "average": avg,
        "streak": streak,
        "total_entries": total,
        "notes_correlation": notes_correlation,
    }
