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
    pool_pre_ping=True,
    pool_recycle=3600,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db():
    # The project is PostgreSQL-only (16 + pgvector) since #273. The previous
    # SQLite branch created a stale joidy.db and silently skipped migrations
    # and the vector extension, causing schema drift and broken AI features.
    #
    # Creating /data/db was a leftover of that SQLite era: the API stores
    # nothing there (PostgreSQL owns its own volume), and only the worker uses
    # the directory, for its own event log — which it creates itself. The
    # unguarded mkdir could raise PermissionError and abort API startup
    # entirely when /data was not writable (#624).
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    _run_migrations()


# Import all models so they are registered with Base.metadata.
from models import *  # noqa: E402,F401


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
