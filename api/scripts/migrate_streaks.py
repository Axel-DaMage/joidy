import sqlite3
from pathlib import Path

db_path = "./data/db/joidy.db"
# Let's check where the db file is. 
# In docker-compose it's often mapped.

def migrate():
    # If standard path fails, we'll try to find it.
    paths = [db_path, "joidy.db", "./data/db/joidy.db"]
    conn = None
    for p in paths:
        if Path(p).exists():
            print(f"Found DB at {p}")
            conn = sqlite3.connect(p)
            break
    
    if not conn:
        print("DB not found in standard paths.")
        return

    cursor = conn.cursor()
    
    # Check current columns
    cursor.execute("PRAGMA table_info(personal_streaks)")
    cols = [col[1] for col in cursor.fetchall()]
    print(f"Current columns: {cols}")

    if "color" not in cols:
        print("Adding color column...")
        cursor.execute("ALTER TABLE personal_streaks ADD COLUMN color TEXT DEFAULT ''")
    
    if "start_date" not in cols:
        print("Adding start_date column...")
        cursor.execute("ALTER TABLE personal_streaks ADD COLUMN start_date DATE")

    if "offset" not in cols:
        print("Adding offset column...")
        cursor.execute("ALTER TABLE personal_streaks ADD COLUMN offset INTEGER DEFAULT 0")

    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
