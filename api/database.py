import logging
import re
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.util.exc import CommandError
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

# ``alembic upgrade head`` fails with "Can't locate revision identified by
# '<rev>'" when the DB's alembic_version names a revision that does not exist
# in the running code — i.e. the database was migrated by a NEWER Joidy
# version (#1489).
_MISSING_REVISION_RE = re.compile(r"Can't locate revision identified by '([^']+)'")


def _missing_revision_id(exc: Exception) -> str | None:
    # CommandError is the documented type for this failure, but match on the
    # message text as well in case a different alembic version raises another
    # exception type (#1489).
    if isinstance(exc, CommandError) or "Can't locate revision" in str(exc):
        match = _MISSING_REVISION_RE.search(str(exc))
        if match:
            return match.group(1)
    return None


def _current_db_revisions() -> set[str]:
    # Best-effort probe of the DB's recorded alembic revisions, used to tell
    # apart the two causes of "Can't locate revision" (#1585):
    #   - the DB's alembic_version names a revision absent from the code
    #     (migrated by a NEWER Joidy version, #1489), or
    #   - a migration file in the code references a deleted down_revision,
    #     so alembic fails loading the revision map before ever reading
    #     the DB (broken chain — updating the code would not help).
    # Reads ALL rows: alembic_version can hold multiple rows in
    # multi-head/branch states, and the missing revision may be recorded
    # in any of them (#1598).
    # Returns an empty set whenever the revisions cannot be determined —
    # the alembic_version table may not exist yet, the DB may be
    # unreachable, or the probe itself may error. Any failure here must
    # never mask the original migration error: callers fall back to the
    # generic path.
    try:
        with engine.connect() as conn:
            return set(conn.execute(text("SELECT version_num FROM alembic_version")).scalars().all())
    except Exception:
        logger.debug(
            "Could not read alembic_version while diagnosing migration failure",
            exc_info=True,
        )
        return set()


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
    except Exception as exc:
        missing_rev = _missing_revision_id(exc)
        # Only blame the DB when the missing revision IS recorded in its
        # alembic_version — which can hold multiple rows in multi-head
        # states, so membership-test the full set (#1598). If the revision
        # map itself is broken (a code migration references a deleted
        # down_revision) the probe finds only other — or no — versions,
        # and the "DB is newer" verdict would misdiagnose the failure
        # (#1585). A probe failure also lands here.
        if missing_rev is not None and missing_rev in _current_db_revisions():
            # Fail loudly: the previous behavior was a generic alembic
            # traceback that crash-looped the container with no hint about
            # the actual cause or the fix (#1489).
            logger.critical(
                "FATAL: database schema is NEWER than the running Joidy version.\n"
                "The database was migrated by a NEWER Joidy version "
                "(alembic revision '%s'), but this image/code is OLDER and "
                "does not contain that revision.\n"
                "This commonly happens when switching between "
                "release/local-build/dev channels.\n"
                "ACTION REQUIRED: update to a newer Joidy image or check out "
                "a newer version of the code. Do NOT attempt to downgrade "
                "the database.",
                missing_rev,
                exc_info=True,
            )
        else:
            logger.exception("Failed to apply database migrations")
        raise
