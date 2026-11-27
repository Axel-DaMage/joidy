"""Personal Streaks Service — extracted from routers for better separation of concerns."""

from datetime import date, timedelta
from typing import cast

from models.personal_streaks import PersonalStreak, StreakCheckIn
from services.timezone_utils import get_local_today
from sqlalchemy import insert
from sqlalchemy.orm import Session

# Per-request cap on the auto-backfill window (#1321). Without it, a streak
# whose start_date is absurdly old (e.g. 0001-01-01 — previously accepted, or
# already stored in pre-validation databases) iterated day-by-day and inserted
# ~740k StreakCheckIn rows inside a single create/update request — a DoS plus
# DB bloat. Only the most recent MAX_BACKFILL_DAYS days are auto-generated;
# older history is simply left empty rather than rejecting the request.
MAX_BACKFILL_DAYS = 400


def backfill_streak_history(db: Session, streak: PersonalStreak) -> None:
    """Generates missing check-ins from start_date up to yesterday."""
    if not streak.start_date:
        return

    today = get_local_today()
    end_date = streak.created_at.date() if streak.created_at else today
    # Clamp the fill start so a single call never iterates more than
    # MAX_BACKFILL_DAYS days; the every_n anchor below still uses the real
    # start_date so day-0 alignment is preserved.
    current = max(streak.start_date, end_date - timedelta(days=MAX_BACKFILL_DAYS))

    existing_dates = {c.check_date for c in streak.checkins}

    new_dates: list[date] = []
    while current < end_date:
        if current not in existing_dates:
            should_add = False
            if streak.frequency == "daily" or not streak.frequency:
                should_add = True
            elif streak.frequency == "every_n":
                days_since_start = (current - streak.start_date).days
                if days_since_start % (streak.frequency_days or 1) == 0:
                    should_add = True

            if should_add:
                new_dates.append(current)  # type: ignore[arg-type]

        current += timedelta(days=1)

    if new_dates:
        # One executemany INSERT for the whole backfill — the per-row
        # repository add() used to flush()+refresh() every inserted day, ~2
        # round trips × up to MAX_BACKFILL_DAYS rows in a single request, and
        # even a plain add_all() can't batch because created_at defaults to a
        # SQL expression (func.now()) (#1526). Rows are committed below and the
        # expired streak.checkins reloads with them.
        db.execute(
            insert(StreakCheckIn),
            [
                {"streak_id": streak.id, "check_date": check_date, "note": "Auto-generado (Migración)"}
                for check_date in new_dates
            ],
        )
        # Instrumented Column attribute: declared Column[int] but stores a
        # plain int at runtime.
        streak.total_checkins = (streak.total_checkins or 0) + len(new_dates)  # type: ignore[assignment]
        db.commit()
        db.refresh(streak)


def compute_streak(
    checkin_dates: list[date],
    frequency: str = "daily",
    frequency_days: int = 1,
    snowball_mode: bool = False,
) -> tuple[int, int]:
    """Returns (current_streak, longest_streak) considering frequency settings.

    In snowball_mode (persistent streak), missed days never break or reset
    the counter — the streak continues accumulating continuously like a
    snowball.

    Uses the most recent check-in date as the reference point when today is
    not in the check-in set, instead of relying solely on get_local_today().
    This avoids timezone mismatches between the frontend (which sends local
    browser dates) and the backend (which defaults to UTC). See issue #864.
    """
    if not checkin_dates:
        return 0, 0

    dates_set = set(checkin_dates)

    if snowball_mode:
        count = len(dates_set)
        return count, count
    today = get_local_today()
    # Use the most recent check-in date as the reference "today" when the
    # server's today is not in the check-in set. This handles the case where
    # the user's local date differs from the server's UTC date.
    most_recent = max(dates_set)

    if frequency == "every_n" and frequency_days > 1:
        sorted_dates = sorted(dates_set, reverse=True)
        current = 0
        for i, d in enumerate(sorted_dates):
            if i == 0:
                # Allow the most recent check-in to be within frequency_days
                # of either server-today or the most recent check-in date.
                reference = today if today in dates_set else most_recent
                if (reference - d).days > frequency_days:
                    break
                current = 1
            else:
                gap = (sorted_dates[i - 1] - d).days
                if gap <= frequency_days:
                    current += 1
                else:
                    break

        sorted_asc = sorted(dates_set)
        longest = 1
        run = 1
        for i in range(1, len(sorted_asc)):
            gap = (sorted_asc[i] - sorted_asc[i - 1]).days
            if gap <= frequency_days:
                run += 1
                longest = max(longest, run)
            else:
                run = 1
        return current, max(longest, run) if sorted_asc else 0
    else:
        current = 0
        # Start from server-today; if not checked in, try yesterday; if
        # neither is in the set, fall back to the most recent check-in date
        # to avoid showing 0 when the timezone offset causes a date mismatch.
        cursor = today
        if cursor not in dates_set:
            cursor -= timedelta(days=1)
        if cursor not in dates_set:
            cursor = most_recent

        while cursor in dates_set:
            current += 1
            cursor -= timedelta(days=1)

        sorted_dates = sorted(dates_set)
        longest = 1
        run = 1
        for i in range(1, len(sorted_dates)):
            if (sorted_dates[i] - sorted_dates[i - 1]).days == 1:
                run += 1
                longest = max(longest, run)
            else:
                run = 1

        return current, longest


def calculate_streak_stats(streak: PersonalStreak) -> dict:
    """Calculate derived stats for a streak."""
    checkin_dates = [c.check_date for c in streak.checkins]
    current, longest = compute_streak(
        checkin_dates,
        cast(str, streak.frequency or "daily"),
        cast(int, streak.frequency_days or 1),
        snowball_mode=bool(getattr(streak, "snowball_mode", False)),
    )
    return {
        "current_streak": current,
        "longest_streak": longest,
    }
