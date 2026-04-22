from datetime import date, timedelta

def _compute_streak(checkin_dates: list[date], frequency: str = "daily", frequency_days: int = 1) -> tuple[int, int]:
    if not checkin_dates:
        return 0, 0

    dates_set = set(checkin_dates)
    today = date.today()

    if frequency == "every_n" and frequency_days > 1:
        # Same as backend
        pass
    else:
        # Daily logic
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

today = date.today()
print(_compute_streak([today - timedelta(days=1)]))
