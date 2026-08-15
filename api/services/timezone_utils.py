"""Timezone-aware day-boundary helpers for streak and gamification logic.

The Docker container runs in UTC by default, but the user's local calendar day
may differ. These helpers compute "today" and "now" in the configured user
timezone (``settings.user_timezone``, an IANA zone name) so that streaks, daily
activity, XP timestamps, and mood entries use the user-local day rather than the
server UTC day.

Timestamps stored in the DB should still be UTC; only the "what day is it for
the user" logic should use these helpers. See issue #650.
"""

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from config import settings

# Cache the ZoneInfo object — constructing it on every call is wasteful and the
# setting rarely changes at runtime.
_tz_cache: ZoneInfo | None = None
_tz_cache_key: str | None = None


def get_user_tz() -> ZoneInfo:
    """Return the configured user timezone as a ``ZoneInfo`` instance.

    Falls back to UTC if the configured zone name is invalid.
    """
    global _tz_cache, _tz_cache_key
    key = settings.user_timezone or "UTC"
    if _tz_cache is None or _tz_cache_key != key:
        try:
            _tz_cache = ZoneInfo(key)
        except ZoneInfoNotFoundError:
            _tz_cache = ZoneInfo("UTC")
        _tz_cache_key = key
    return _tz_cache


def get_local_now() -> datetime:
    """Return the current moment as a timezone-aware datetime in the user tz."""
    return datetime.now(get_user_tz())


def get_local_today() -> date:
    """Return today's date in the configured user timezone.

    Use this instead of ``datetime.now(timezone.utc).date()`` or
    ``date.today()`` for any day-boundary calculation (streaks, daily activity,
    XP idempotency, mood entries, goal expiry).
    """
    return get_local_now().date()


def to_utc_datetime(local_day: date) -> datetime:
    """Convert a user-local calendar day to a UTC-aware datetime at midnight.

    Useful when querying DB columns that store UTC timestamps but the query
    boundary should be the user-local day (e.g. "notes created today").
    The returned datetime is the start of ``local_day`` expressed in UTC.
    """
    # Midnight in the user tz, then convert to UTC.
    local_midnight = datetime.combine(local_day, datetime.min.time(), tzinfo=get_user_tz())
    return local_midnight.astimezone(timezone.utc)
