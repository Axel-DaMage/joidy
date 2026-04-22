from pathlib import Path
import logging
from alembic import command
from alembic.config import Config

import sqlite_vec
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import settings


logger = logging.getLogger(__name__)


def _setup_sqlite(dbapi_connection, connection_record):
    dbapi_connection.enable_load_extension(True)
    sqlite_vec.load(dbapi_connection)
    dbapi_connection.enable_load_extension(False)
    dbapi_connection.execute("PRAGMA journal_mode=WAL")
    dbapi_connection.execute("PRAGMA foreign_keys=ON")
    dbapi_connection.execute("PRAGMA synchronous=NORMAL")


engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
)

event.listen(engine, "connect", _setup_sqlite)

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
