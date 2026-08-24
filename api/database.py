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


# Stable advisory-lock key used to serialize Alembic migrations across
# uvicorn workers on cold start (#816). With ``--workers N`` every worker
# runs the FastAPI lifespan concurrently, and each one used to call
# ``alembic upgrade head`` at the same time — the loser of the race crashed
# its child process, flap-looping the container until migrations settled.
# ``pg_advisory_lock`` is session-scoped and blocks until the holder
# releases it, so the second worker simply waits for the first to finish,
# then re-runs ``upgrade head`` which is a no-op (already at head).
# 0x4A4F494459 = ASCII "JOIDY"; suffix disambiguates from future locks.
_ALEMBIC_ADVISORY_LOCK_KEY = 0x4A4F494459000001


def _run_migrations() -> None:
    alembic_ini = Path(__file__).resolve().parent / "alembic.ini"
    if not alembic_ini.exists():
        logger.warning("alembic.ini not found at %s, skipping migrations", alembic_ini)
        return

    cfg = Config(str(alembic_ini))
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parent / "alembic"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)

    # Only PostgreSQL supports advisory locks. The SQLite fallback used by
    # some unit tests stubs ``init_db`` away entirely (conftest.py), so this
    # branch is effectively only reached in production against PostgreSQL.
    use_advisory_lock = engine.dialect.name == "postgresql"

    try:
        if use_advisory_lock:
            # Hold the lock for the whole migration window. ``pg_advisory_lock``
            # blocks the calling session until the key is available — exactly
            # what we want: workers serialize instead of racing.
            with engine.connect() as lock_conn:
                lock_conn.execute(
                    text("SELECT pg_advisory_lock(:key)"),
                    {"key": _ALEMBIC_ADVISORY_LOCK_KEY},
                )
                try:
                    command.upgrade(cfg, "head")
                finally:
                    lock_conn.execute(
                        text("SELECT pg_advisory_unlock(:key)"),
                        {"key": _ALEMBIC_ADVISORY_LOCK_KEY},
                    )
                    lock_conn.commit()
        else:
            command.upgrade(cfg, "head")
        logger.info("Database migrations applied successfully")
    except Exception:
        logger.exception("Failed to apply database migrations")
        raise
