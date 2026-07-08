import logging
import sqlite3
from pathlib import Path

DB_PATH = Path("/data/db/joidy.db")
REQUIRED_TABLES = {
    "alembic_version",
    "notes",
    "tags",
    "note_tags",
    "tag_cooccurrences",
    "embedding_failures",
}

logger = logging.getLogger(__name__)


def check_db_health() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"Database not found at {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    finally:
        conn.close()

    existing = {r[0] for r in rows}
    missing = sorted(REQUIRED_TABLES - existing)
    if missing:
        raise SystemExit(f"Missing tables: {missing}")

    logger.info("DB health OK")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    check_db_health()
