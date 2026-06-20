from datetime import date, timedelta
def _compute_streak(checkin_dates: list[date], frequency: str = "daily", frequency_days: int = 1) -> tuple[int, int]:
    if not checkin_dates:
        return 0, 0

    dates_set = set(checkin_dates)
    today = date.today()

    if frequency == "every_n" and frequency_days > 1:
        # For every-N-days: streak counts how many consecutive "on-time" check-ins
        sorted_dates = sorted(dates_set, reverse=True)
        current = 0
        # Walk from most recent check-in backwards
        for i, d in enumerate(sorted_dates):
            if i == 0:
                # Most recent must be within frequency_days of today
                if (today - d).days > frequency_days:
                    break
                current = 1
            else:
                gap = (sorted_dates[i - 1] - d).days
                if gap <= frequency_days:
                    current += 1
                else:
                    break

        # Longest streak
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
        # Daily: original logic
        current = 0
        cursor = today
        
        # If today is not checked in, we should check yesterday.
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
        longest = max(longest, run) if sorted_dates else 0
        return current, longest

t = date.today()
print("Just today:",_compute_streak([t]))
print("Missing today, checked yesterday:",_compute_streak([t - timedelta(days=1)]))
print("Missing both:",_compute_streak([t - timedelta(days=2)]))
print("Checked yesterday and today:",_compute_streak([t, t - timedelta(days=1)]))
print("Long gap:",_compute_streak([t, t - timedelta(days=1), t - timedelta(days=5), t - timedelta(days=6)]))
