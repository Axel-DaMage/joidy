"""Holistic Analytics Service — single-round-trip overview aggregation (#1499).

Powers ``GET /analytics/overview``: a combined activity / XP / seasonality /
mood / goals / streaks / GitHub payload for the holistic analytics page.

XP events and streak records are the honest clocks for the time series —
``Goal.updated_at``/``completed_at`` move on any write and must NOT be used
as activity timestamps.
"""

import math
from datetime import UTC, date, datetime, time, timedelta

from models.gamification import UserStats, XPEvent
from models.github import GitHubEvent, GitHubEventType, GitHubRepo, GitHubRepoStatus
from models.goal import Goal, GoalState, GoalTemporality
from models.mood_entry import MoodEntry
from models.note import Note
from models.personal_streaks import PersonalStreak, StreakCheckIn
from services.timezone_utils import get_local_today
from sqlalchemy import case, extract, func
from sqlalchemy.orm import Session

GITHUB_WEEKS = 12
CHECKIN_RATE_WINDOW_DAYS = 30

# Goal states counted as "abandoned" in the goals funnel.
_ABANDONED_STATES = {GoalState.CANCELLED.value, GoalState.PAUSED.value, GoalState.FAILED.value}

# GitHub webhook event types → output bucket keys (issue_comment → comments).
_EVENT_KEY = {
    GitHubEventType.PUSH.value: "pushes",
    GitHubEventType.PULL_REQUEST.value: "pull_requests",
    GitHubEventType.ISSUES.value: "issues",
    GitHubEventType.ISSUE_COMMENT.value: "comments",
}


def get_overview(db: Session, user_id: int, days: int = 180) -> dict:
    """Aggregate the holistic analytics overview for the last ``days`` days."""
    if days < 1:
        days = 1
    if days > 366:
        days = 366

    now = datetime.now(UTC)
    since = now - timedelta(days=days)
    today = now.date()
    # The daily series covers ``days`` calendar days ending today.
    window_start = today - timedelta(days=days - 1)

    stats = db.query(UserStats).filter(UserStats.id == 1).first()
    daily_activity, xp_map = _daily_activity(db, days, now, since)

    return {
        "days": days,
        "daily_activity": daily_activity,
        "xp_by_type": _xp_by_type(db, since),
        "seasonality": _seasonality(db, since),
        "mood_activity": _mood_activity(db, user_id, window_start, xp_map),
        "goals": _goals(db),
        "streaks": _streaks(db, stats),
        "github": _github(db, today),
        "summary": _summary(daily_activity, stats, days),
    }


def _daily_activity(db: Session, days: int, now: datetime, since: datetime) -> tuple[list[dict], dict[str, int]]:
    """One row per day (oldest → newest), zero-filled for inactive days.

    Returns the row list plus a {ISO date: xp} map reused by mood_activity.
    """
    xp_rows = (
        db.query(
            func.date(XPEvent.created_at).label("d"),
            func.coalesce(func.sum(XPEvent.xp), 0).label("xp"),
            func.count(XPEvent.id).label("events"),
            func.coalesce(func.sum(case((XPEvent.event_type == "goal_completed", 1), else_=0)), 0).label(
                "goals_completed"
            ),
            func.coalesce(func.sum(case((XPEvent.event_type == "pomodoro_completed", 1), else_=0)), 0).label(
                "pomodoros"
            ),
        )
        .filter(XPEvent.created_at >= since)
        .group_by(func.date(XPEvent.created_at))
        .all()
    )
    notes_rows = (
        db.query(func.date(Note.created_at).label("d"), func.count(Note.id).label("c"))
        .filter(Note.created_at >= since)
        .group_by(func.date(Note.created_at))
        .all()
    )

    xp_by_day = {str(r.d)[:10]: r for r in xp_rows}
    notes_by_day = {str(r.d)[:10]: r.c for r in notes_rows}
    xp_map = {day: int(r.xp) for day, r in xp_by_day.items()}

    daily = []
    for i in reversed(range(days)):
        day_str = (now - timedelta(days=i)).date().isoformat()
        row = xp_by_day.get(day_str)
        daily.append(
            {
                "date": day_str,
                "xp": int(row.xp) if row else 0,
                "events": int(row.events) if row else 0,
                "goals_completed": int(row.goals_completed) if row else 0,
                "pomodoros": int(row.pomodoros) if row else 0,
                "notes": notes_by_day.get(day_str, 0),
            }
        )
    return daily, xp_map


def _xp_by_type(db: Session, since: datetime) -> list[dict]:
    """XP totals per event type over the window, sorted by xp descending."""
    rows = (
        db.query(
            XPEvent.event_type.label("event_type"),
            func.coalesce(func.sum(XPEvent.xp), 0).label("xp"),
            func.count(XPEvent.id).label("c"),
        )
        .filter(XPEvent.created_at >= since)
        .group_by(XPEvent.event_type)
        .all()
    )
    entries = [{"type": r.event_type, "xp": int(r.xp), "count": int(r.c)} for r in rows]
    return sorted(entries, key=lambda e: e["xp"], reverse=True)


def _seasonality(db: Session, since: datetime) -> dict:
    """Weekday × hour density of XP events over the window.

    ``extract('dow', ...)`` is Sunday=0 on both PostgreSQL and SQLite (via
    STRFTIME('%w')); it is shifted to Python ``datetime.weekday()`` (Monday=0).
    """
    dow_col = extract("dow", XPEvent.created_at)
    hour_col = extract("hour", XPEvent.created_at)
    rows = (
        db.query(
            dow_col.label("dow"),
            hour_col.label("hour"),
            func.count(XPEvent.id).label("c"),
        )
        .filter(XPEvent.created_at >= since)
        .group_by(dow_col, hour_col)
        .all()
    )
    counts: dict[tuple[int, int], int] = {}
    for r in rows:
        weekday = (int(r.dow) + 6) % 7  # Sunday=0 → Monday=0
        hour = int(r.hour)
        key = (weekday, hour)
        counts[key] = counts.get(key, 0) + int(r.c)
    cells = [{"weekday": w, "hour": h, "count": c} for (w, h), c in sorted(counts.items())]
    return {"cells": cells, "max": max((c["count"] for c in cells), default=0)}


def _mood_activity(db: Session, user_id: int, window_start: date, xp_map: dict[str, int]) -> dict:
    """Daily mood joined with same-day XP, plus the Pearson correlation."""
    entries = (
        db.query(MoodEntry)
        .filter(MoodEntry.user_id == user_id, MoodEntry.entry_date >= window_start)
        .order_by(MoodEntry.entry_date.asc())
        .all()
    )
    points = [
        {
            "date": e.entry_date.isoformat(),
            "mood": e.score,
            "xp": xp_map.get(e.entry_date.isoformat(), 0),
        }
        for e in entries
    ]
    return {
        "points": points,
        "pearson_r": _pearson([p["mood"] for p in points], [p["xp"] for p in points]),
        "sample_size": len(points),
    }


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    """Pearson product-moment correlation; None when fewer than 3 samples."""
    n = len(xs)
    if n < 3:
        return None
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    denom = math.sqrt(var_x * var_y)
    if denom == 0:
        # Undefined when one side has zero variance; report a neutral 0.0.
        return 0.0
    return round(min(1.0, max(-1.0, cov / denom)), 2)


def _goals(db: Session) -> dict:
    """Goal counts by state, per-temporality aggregates, and lifecycle funnel."""
    rows = db.query(Goal.state, Goal.temporality, Goal.current_value, Goal.target_value).all()

    by_state: dict[str, int] = {}
    temp_groups: dict[str, dict] = {}
    funnel = {"created": len(rows), "activated": 0, "completed": 0, "abandoned": 0}

    for state, temporality, current_value, target_value in rows:
        state_val = state.value if hasattr(state, "value") else str(state)
        temp_val = temporality.value if hasattr(temporality, "value") else str(temporality)

        by_state[state_val] = by_state.get(state_val, 0) + 1
        if state_val != GoalState.INBOX.value:
            funnel["activated"] += 1
        if state_val == GoalState.COMPLETED.value:
            funnel["completed"] += 1
        if state_val in _ABANDONED_STATES:
            funnel["abandoned"] += 1

        group = temp_groups.setdefault(temp_val, {"total": 0, "completed": 0, "failed": 0, "progress": []})
        group["total"] += 1
        if state_val == GoalState.COMPLETED.value:
            group["completed"] += 1
        if state_val == GoalState.FAILED.value:
            group["failed"] += 1
        if target_value and target_value > 0:
            group["progress"].append(current_value / target_value * 100)

    by_temporality = []
    for temp in GoalTemporality:
        group = temp_groups.get(temp.value)
        if not group:
            continue
        avg = round(sum(group["progress"]) / len(group["progress"]), 1) if group["progress"] else 0.0
        by_temporality.append(
            {
                "temporality": temp.value,
                "total": group["total"],
                "completed": group["completed"],
                "failed": group["failed"],
                "avg_progress": min(100.0, max(0.0, avg)),
            }
        )

    return {
        "by_state": by_state,
        "by_temporality": by_temporality,
        "funnel": [
            {"stage": stage, "count": funnel[stage]} for stage in ("created", "activated", "completed", "abandoned")
        ],
    }


def _streaks(db: Session, stats: UserStats | None) -> dict:
    """Global XP streak (UserStats singleton) + personal-streak check-in stats.

    ``checkin_rate_30d`` mirrors ``/personal-streaks/stats``: for each active
    streak, ``30 // frequency_days`` possible check-ins vs. actual check-ins in
    the last 30 days.
    """
    active_freqs = [
        row[0] or 1
        for row in db.query(PersonalStreak.frequency_days)
        .filter(PersonalStreak.is_archived == False)  # noqa: E712 -- SQLAlchemy column comparison
        .all()
    ]
    total_checkins = db.query(func.count(StreakCheckIn.id)).scalar() or 0

    thirty_ago = get_local_today() - timedelta(days=CHECKIN_RATE_WINDOW_DAYS)
    possible = sum(CHECKIN_RATE_WINDOW_DAYS // freq for freq in active_freqs)
    actual = (
        db.query(func.count(StreakCheckIn.id))
        .join(PersonalStreak, StreakCheckIn.streak_id == PersonalStreak.id)
        .filter(
            PersonalStreak.is_archived == False,  # noqa: E712 -- SQLAlchemy column comparison
            StreakCheckIn.check_date >= thirty_ago,
        )
        .scalar()
        or 0
    )
    checkin_rate = round(actual / possible * 100, 1) if possible > 0 else 0

    return {
        "current_streak": stats.current_streak if stats else 0,
        "longest_streak": stats.longest_streak if stats else 0,
        "active_streaks": len(active_freqs),
        "total_checkins": total_checkins,
        "checkin_rate_30d": checkin_rate,
    }


def _github(db: Session, today: date) -> dict:
    """Last 12 ISO weeks of GitHub webhook activity, Monday-bucketed.

    ``available`` is true when any repo is ACTIVE or any event has been
    received; when unavailable the weekly list is empty.
    """
    has_repo = db.query(GitHubRepo.id).filter(GitHubRepo.status == GitHubRepoStatus.ACTIVE).first() is not None
    has_events = db.query(GitHubEvent.id).first() is not None
    if not (has_repo or has_events):
        return {"available": False, "weekly": []}

    current_monday = today - timedelta(days=today.weekday())
    first_monday = current_monday - timedelta(weeks=GITHUB_WEEKS - 1)
    window_start = datetime.combine(first_monday, time.min)

    rows = (
        db.query(
            func.date(GitHubEvent.created_at).label("d"),
            GitHubEvent.event_type.label("event_type"),
            func.count(GitHubEvent.id).label("c"),
        )
        .filter(GitHubEvent.created_at >= window_start)
        .group_by(func.date(GitHubEvent.created_at), GitHubEvent.event_type)
        .all()
    )

    buckets: dict[str, dict] = {}
    for r in rows:
        event_day = date.fromisoformat(str(r.d)[:10])
        week_start = (event_day - timedelta(days=event_day.weekday())).isoformat()
        bucket = buckets.setdefault(week_start, {"pushes": 0, "pull_requests": 0, "issues": 0, "comments": 0})
        event_type = r.event_type.value if hasattr(r.event_type, "value") else str(r.event_type)
        key = _EVENT_KEY.get(event_type)
        if key:
            bucket[key] += int(r.c)

    weekly = []
    for i in range(GITHUB_WEEKS):
        monday = first_monday + timedelta(weeks=i)
        bucket = buckets.get(monday.isoformat(), {})
        weekly.append(
            {
                "week_start": monday.isoformat(),
                "pushes": bucket.get("pushes", 0),
                "pull_requests": bucket.get("pull_requests", 0),
                "issues": bucket.get("issues", 0),
                "comments": bucket.get("comments", 0),
            }
        )
    return {"available": True, "weekly": weekly}


def _summary(daily_activity: list[dict], stats: UserStats | None, days: int) -> dict:
    """Headline figures derived from the daily series + UserStats singleton."""
    total_window_xp = sum(row["xp"] for row in daily_activity)
    best = max(daily_activity, key=lambda row: row["xp"])
    return {
        "total_xp": stats.total_xp if stats else 0,
        "active_days": sum(1 for row in daily_activity if row["events"] > 0),
        "avg_daily_xp": round(total_window_xp / days, 1),
        "best_day": {"date": best["date"], "xp": best["xp"]} if best["xp"] > 0 else None,
    }
