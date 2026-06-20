"""Personal Streaks Service — extracted from routers for better separation of concerns."""
from datetime import date, timedelta
from sqlalchemy.orm import Session
from models.personal_streaks import PersonalStreak, StreakCheckIn


def backfill_streak_history(db: Session, streak: PersonalStreak) -> None:
    """Generates missing check-ins from start_date up to yesterday."""
    if not streak.start_date:
        return

    today = date.today()
    end_date = streak.created_at.date() if streak.created_at else today
    current = streak.start_date

    existing_dates = {c.check_date for c in streak.checkins}

    added_count = 0
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
                ci = StreakCheckIn(
                    streak_id=streak.id,
                    check_date=current,
                    note="Auto-generado (Migración)"
                )
                db.add(ci)
                added_count += 1

        current += timedelta(days=1)

    if added_count > 0:
        streak.total_checkins = (streak.total_checkins or 0) + added_count
        db.commit()
        db.refresh(streak)


def compute_streak(checkin_dates: list[date], frequency: str = "daily", frequency_days: int = 1) -> tuple[int, int]:
    """Returns (current_streak, longest_streak) considering frequency settings."""
    if not checkin_dates:
        return 0, 0

    dates_set = set(checkin_dates)
    today = date.today()

    if frequency == "every_n" and frequency_days > 1:
        sorted_dates = sorted(dates_set, reverse=True)
        current = 0
        for i, d in enumerate(sorted_dates):
            if i == 0:
                if (today - d).days > frequency_days:
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
        cursor = today

        if cursor not in dates_set:
            cursor -= timedelta(days=1)

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
        streak.frequency or "daily",
        streak.frequency_days or 1
    )
    return {
        "current_streak": current,
        "longest_streak": longest,
    }