import sys
import os
from datetime import date, timedelta

# Add api directory to path to import models and database
sys.path.append(os.path.join(os.getcwd(), 'api'))

from database import SessionLocal
from models.personal_streaks import PersonalStreak, StreakCheckIn

def backfill():
    db = SessionLocal()
    try:
        streaks = db.query(PersonalStreak).all()
        today = date.today()
        
        for streak in streaks:
            if not streak.start_date or streak.start_date >= today:
                continue
                
            print(f"Checking streak: {streak.name} (Start: {streak.start_date})")
            
            existing_dates = {c.check_date for c in streak.checkins}
            current = streak.start_date
            added = 0
            
            while current < today:
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
                        added += 1
                
                current += timedelta(days=1)
            
            if added > 0:
                print(f"  Added {added} check-ins to {streak.name}")
                streak.total_checkins = (streak.total_checkins or 0) + added
        
        db.commit()
        print("Done!")
    finally:
        db.close()

if __name__ == "__main__":
    backfill()
