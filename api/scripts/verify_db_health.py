import logging

from sqlalchemy import inspect

from config import settings
from database import engine

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
    inspector = inspect(engine)
    existing = set(inspector.get_table_names())
    missing = sorted(REQUIRED_TABLES - existing)
    if missing:
        raise SystemExit(f"Missing tables: {missing}")

    logger.info("DB health OK (engine=%s)", settings.database_url.split("@")[-1])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    check_db_health()
