import os
import random
from datetime import datetime, timedelta, date

from database import SessionLocal
from models.goal import Goal, GoalTemporality, GoalMeasurement, GoalState, GoalFailConfig
from models.planning import PlanningAssignment
from models.note import Note, Tag

def seed():
    db = SessionLocal()
    print("Clearing old goals...")
    db.query(PlanningAssignment).delete()
    db.query(Goal).delete()
    db.commit()

    print("Generating goals and streaks...")
    today = datetime.utcnow()
    
    # 1. Past 180 days streak (Heatmap)
    for i in range(180, -1, -1):
        day_date = today - timedelta(days=i)
        
        # 85% chance to complete goals this day
        completed_today = random.random() < 0.85
        
        num_goals = random.randint(1, 3)
        for g in range(num_goals):
            state = GoalState.COMPLETED if completed_today else GoalState.FAILED
            is_completed = completed_today
            
            goal = Goal(
                title=f"Objetivo de Prueba {i}-{g+1}",
                description="Dato generado automáticamente.",
                temporality=GoalTemporality.DAILY,
                measurement_type=GoalMeasurement.COUNT,
                target_value=1.0,
                current_value=1.0 if completed_today else 0.0,
                state=state,
                is_completed=is_completed,
                completed_at=day_date if completed_today else None,
                created_at=day_date - timedelta(hours=12),
                updated_at=day_date,
                color=random.choice(["#c8a96e", "#10b981", "#3b82f6", "#ef4444"])
            )
            db.add(goal)
            db.flush()
            
            if completed_today or random.random() < 0.5:
                assign = PlanningAssignment(
                    date=day_date.date(),
                    goal_id=goal.id,
                    created_at=day_date - timedelta(hours=12)
                )
                db.add(assign)
                
    # 2. Add some active current goals
    temps = [GoalTemporality.DAILY, GoalTemporality.WEEKLY, GoalTemporality.MONTHLY, GoalTemporality.ANNUAL]
    for _ in range(40):
        target = random.randint(1, 20)
        goal = Goal(
            title=f"Objetivo Activo {_}",
            description="Meta actual pendiente.",
            temporality=random.choice(temps),
            measurement_type=random.choice([GoalMeasurement.COUNT, GoalMeasurement.PERCENT]),
            state=GoalState.ACTIVE,
            target_value=target,
            current_value=random.randint(0, target - 1),
            fail_config=random.choice([GoalFailConfig.STATIC, GoalFailConfig.ROLLOVER, GoalFailConfig.SNOWBALL]),
            color=random.choice(["#c8a96e", "#10b981", "#3b82f6", "#ef4444", "#ec4899", "#8b5cf6"])
        )
        db.add(goal)
        db.flush()
        
        # Assign many to today or upcoming days
        if random.random() < 0.7:
            offset = random.randint(0, 5)
            assign_date = today.date() + timedelta(days=offset)
            assign = PlanningAssignment(
                date=assign_date,
                goal_id=goal.id,
                created_at=today
            )
            db.add(assign)

    db.commit()
    db.close()
    print("Seed complete.")

if __name__ == "__main__":
    seed()
