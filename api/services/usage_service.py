"""Usage Tracking Service — internal usage metrics for the analytics dashboard (#251, #250).

Records lightweight usage events (page views, feature use, session start/end)
and aggregates them into summaries consumed by the analytics dashboard. Events
are only recorded while the web app is in the foreground (the frontend pauses
tracking on ``visibilitychange`` → hidden).
"""

from datetime import UTC, datetime, timedelta

from models.usage_event import UsageEvent
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

# Event types tracked by the frontend usage store.
EVENT_PAGE_VIEW = "page_view"
EVENT_FEATURE_USE = "feature_use"
EVENT_SESSION_START = "session_start"
EVENT_SESSION_END = "session_end"

VALID_EVENT_TYPES = {
    EVENT_PAGE_VIEW,
    EVENT_FEATURE_USE,
    EVENT_SESSION_START,
    EVENT_SESSION_END,
}


def track_event(
    db: Session,
    user_id: int,
    event_type: str,
    event_data: dict | None = None,
) -> UsageEvent:
    """Record a single usage event for ``user_id``.

    Unknown event types are rejected to keep the analytics surface small and
    predictable. ``event_data`` is stored as-is (JSON column).
    """
    if event_type not in VALID_EVENT_TYPES:
        raise ValueError(f"Unknown usage event type: {event_type}")

    event = UsageEvent(
        user_id=user_id,
        event_type=event_type,
        event_data=event_data,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def get_usage_summary(db: Session, user_id: int, days: int = 30) -> dict:
    """Aggregate usage over the last ``days`` days.

    Returns:
        - ``total_events``: count of all events in the window.
        - ``session_count``: number of ``session_start`` events.
        - ``active_days``: distinct calendar days with any event.
        - ``avg_session_duration_min``: mean minutes between paired
          ``session_start`` and ``session_end`` events (0 when no pairs).
        - ``top_features``: list of ``{feature, count}`` sorted desc (top 10).
        - ``top_pages``: list of ``{path, count}`` sorted desc (top 10).
    """
    if days < 1:
        days = 1
    if days > 366:
        days = 366

    now = datetime.now(UTC)
    since = now - timedelta(days=days)

    base = db.query(UsageEvent).filter(
        UsageEvent.user_id == user_id,
        UsageEvent.created_at >= since,
    )

    total_events = base.count()
    session_count = base.filter(UsageEvent.event_type == EVENT_SESSION_START).count()

    active_days = (
        db.query(func.count(func.distinct(func.date(UsageEvent.created_at))))
        .filter(
            UsageEvent.user_id == user_id,
            UsageEvent.created_at >= since,
        )
        .scalar()
        or 0
    )

    # Average session duration: pair each session_start with the next
    # session_end that follows it. This is an approximation (no explicit
    # session id) but sufficient for a lightweight dashboard.
    #
    # Sessions longer than MAX_SESSION_MIN are discarded as outliers — they
    # typically result from missing session_end events (e.g. tab closed
    # without firing pagehide) rather than genuine usage (#563).
    MAX_SESSION_MIN = 480  # 8 hours
    # Only the timestamp is needed to pair starts with ends — project the
    # single column instead of hydrating full UsageEvent ORM rows (#1523).
    starts = (
        base.with_entities(UsageEvent.created_at)
        .filter(UsageEvent.event_type == EVENT_SESSION_START)
        .order_by(UsageEvent.created_at.asc())
        .all()
    )
    ends = (
        base.with_entities(UsageEvent.created_at)
        .filter(UsageEvent.event_type == EVENT_SESSION_END)
        .order_by(UsageEvent.created_at.asc())
        .all()
    )
    durations: list[float] = []
    end_idx = 0
    for s in starts:
        # Find the first end event after this start.
        while end_idx < len(ends) and ends[end_idx].created_at < s.created_at:
            end_idx += 1
        if end_idx < len(ends):
            delta = ends[end_idx].created_at - s.created_at
            duration_min = delta.total_seconds() / 60.0
            if duration_min <= MAX_SESSION_MIN:
                durations.append(duration_min)
            end_idx += 1
    avg_session_duration_min = round(sum(durations) / len(durations), 2) if durations else 0.0

    top_features = _top_event_values(db, user_id, since, EVENT_FEATURE_USE, "feature", 10)
    top_pages = _top_event_values(db, user_id, since, EVENT_PAGE_VIEW, "path", 10)

    return {
        "days": days,
        "total_events": total_events,
        "session_count": session_count,
        "active_days": active_days,
        "avg_session_duration_min": avg_session_duration_min,
        "top_features": top_features,
        "top_pages": top_pages,
    }


def _top_event_values(
    db: Session,
    user_id: int,
    since: datetime,
    event_type: str,
    data_key: str,
    limit: int,
) -> list[dict]:
    """Aggregate the most common ``event_data[data_key]`` values for an event type.

    The counting runs in SQL (``GROUP BY`` on the extracted JSON value +
    ``LIMIT``) so ``usage_events`` — which grows with every navigation — is
    never hydrated into ORM objects (#1523). ``data_key`` is always a
    server-side literal ("feature"/"path"), never user input, so the JSON key
    lookup is safe. Falls back to a Python-side aggregation when the backend
    doesn't support JSON extraction, keeping the service robust across test
    and production backends.
    """
    value_col = UsageEvent.event_data[data_key].as_string()
    try:
        rows = (
            db.query(value_col.label("v"), func.count(UsageEvent.id).label("c"))
            .filter(
                UsageEvent.user_id == user_id,
                UsageEvent.created_at >= since,
                UsageEvent.event_type == event_type,
                # Missing key / JSON null both extract to NULL — excluded, same
                # as the Python path's ``value is None: continue``.
                value_col.isnot(None),
            )
            .group_by(value_col)
            .order_by(func.count(UsageEvent.id).desc(), value_col.asc())
            .limit(limit)
            .all()
        )
    except SQLAlchemyError:
        return _top_event_values_python(db, user_id, since, event_type, data_key, limit)
    return [{data_key: str(r.v), "count": int(r.c)} for r in rows]


def _top_event_values_python(
    db: Session,
    user_id: int,
    since: datetime,
    event_type: str,
    data_key: str,
    limit: int,
) -> list[dict]:
    """Python-side fallback for backends without JSON extraction support."""
    events = (
        db.query(UsageEvent.event_data)
        .filter(
            UsageEvent.user_id == user_id,
            UsageEvent.created_at >= since,
            UsageEvent.event_type == event_type,
        )
        .all()
    )
    counts: dict[str, int] = {}
    for (event_data,) in events:
        if not event_data:
            continue
        value = event_data.get(data_key)
        if value is None:
            continue
        key = str(value)
        counts[key] = counts.get(key, 0) + 1

    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    return [{data_key: k, "count": v} for k, v in ranked]
