import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from config import settings
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

logger = logging.getLogger(__name__)


engine = create_engine(
    settings.database_url,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Path("/data/db").mkdir(parents=True, exist_ok=True)
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    _run_migrations()


def _run_migrations() -> None:
    alembic_ini = Path(__file__).resolve().parent / "alembic.ini"
    if not alembic_ini.exists():
        logger.warning("alembic.ini not found at %s, skipping migrations", alembic_ini)
        return

    cfg = Config(str(alembic_ini))
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parent / "alembic"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)

    try:
        command.upgrade(cfg, "head")
        logger.info("Database migrations applied successfully")
    except Exception:
        logger.exception("Failed to apply database migrations")
        raise
