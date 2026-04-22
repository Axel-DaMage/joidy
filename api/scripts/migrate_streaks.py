import sqlite3
import logging
from pathlib import Path


logger = logging.getLogger(__name__)

db_path = "./data/db/joidy.db"
# Let's check where the db file is. 
# In docker-compose it's often mapped.

def migrate():
    # If standard path fails, we'll try to find it.
    paths = [db_path, "joidy.db", "./data/db/joidy.db"]
    conn = None
    for p in paths:
        if Path(p).exists():
            logger.info("Found DB at %s", p)
            conn = sqlite3.connect(p)
            break
    
    if not conn:
        logger.error("DB not found in standard paths")
        return

    cursor = conn.cursor()
    
    # Check current columns
    cursor.execute("PRAGMA table_info(personal_streaks)")
    cols = [col[1] for col in cursor.fetchall()]
    logger.info("Current columns: %s", cols)

    if "color" not in cols:
        logger.info("Adding color column")
        cursor.execute("ALTER TABLE personal_streaks ADD COLUMN color TEXT DEFAULT ''")
    
    if "start_date" not in cols:
        logger.info("Adding start_date column")
        cursor.execute("ALTER TABLE personal_streaks ADD COLUMN start_date DATE")

    if "offset" not in cols:
        logger.info("Adding offset column")
        cursor.execute("ALTER TABLE personal_streaks ADD COLUMN offset INTEGER DEFAULT 0")

    conn.commit()
    conn.close()
    logger.info("Migration complete")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    migrate()
