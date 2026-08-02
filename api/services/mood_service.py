"""Mood Tracker Service — daily mood recording and analytics."""

from datetime import date, datetime, timedelta, timezone

from models.mood_entry import MoodEntry
from sqlalchemy.orm import Session


def _today() -> date:
    return datetime.now(timezone.utc).date()


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
    entries = db.query(MoodEntry).filter(MoodEntry.user_id == user_id).order_by(MoodEntry.entry_date.asc()).all()

    if not entries:
        return {
            "average": 0.0,
            "streak": 0,
            "total_entries": 0,
            "notes_correlation": 0.0,
        }

    # Average score
    avg = round(sum(e.score for e in entries) / len(entries), 2)

    # Current streak — consecutive days ending today or yesterday
    dates_set = {e.entry_date for e in entries}
    today = _today()
    cursor = today
    if cursor not in dates_set:
        cursor -= timedelta(days=1)
    streak = 0
    while cursor in dates_set:
        streak += 1
        cursor -= timedelta(days=1)

    # Correlation: fraction of entries that include a note
    with_note = sum(1 for e in entries if e.note and e.note.strip())
    notes_correlation = round(with_note / len(entries), 2)

    return {
        "average": avg,
        "streak": streak,
        "total_entries": len(entries),
        "notes_correlation": notes_correlation,
    }
