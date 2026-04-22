import sqlite3
from pathlib import Path
import logging

import sqlite_vec
from sqlalchemy import create_engine, event, text
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
    from models import note, gamification, skill, goal, personal_streaks
    from models.note import NoteLink  # noqa: F401
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS note_embeddings (
                note_id INTEGER PRIMARY KEY,
                embedding BLOB NOT NULL
            )
        """))
        
        # Auto-migrate personal_streaks
        try:
            res = conn.execute(text("PRAGMA table_info(personal_streaks)"))
            cols = [row[1] for row in res.fetchall()]
            if cols:  # table exists
                migrations = {
                    "color": "ALTER TABLE personal_streaks ADD COLUMN color TEXT DEFAULT ''",
                    "start_date": "ALTER TABLE personal_streaks ADD COLUMN start_date DATE",
                    "offset": "ALTER TABLE personal_streaks ADD COLUMN offset INTEGER DEFAULT 0",
                    "target_date": "ALTER TABLE personal_streaks ADD COLUMN target_date DATE",
                    "category": "ALTER TABLE personal_streaks ADD COLUMN category TEXT DEFAULT 'general'",
                    "theme": "ALTER TABLE personal_streaks ADD COLUMN theme TEXT DEFAULT 'solid'",
                    "frequency": "ALTER TABLE personal_streaks ADD COLUMN frequency TEXT DEFAULT 'daily'",
                    "frequency_days": "ALTER TABLE personal_streaks ADD COLUMN frequency_days INTEGER DEFAULT 1",
                    "icon": "ALTER TABLE personal_streaks ADD COLUMN icon TEXT DEFAULT ''",
                    "is_archived": "ALTER TABLE personal_streaks ADD COLUMN is_archived BOOLEAN DEFAULT 0",
                    "best_streak": "ALTER TABLE personal_streaks ADD COLUMN best_streak INTEGER DEFAULT 0",
                    "total_checkins": "ALTER TABLE personal_streaks ADD COLUMN total_checkins INTEGER DEFAULT 0",
                    "freeze_count": "ALTER TABLE personal_streaks ADD COLUMN freeze_count INTEGER DEFAULT 0",
                    "freeze_used": "ALTER TABLE personal_streaks ADD COLUMN freeze_used INTEGER DEFAULT 0",
                }
                for col_name, sql in migrations.items():
                    if col_name not in cols:
                        logger.info("[migrate] Adding column personal_streaks.%s", col_name)
                        conn.execute(text(sql))
        except Exception as e:
            logger.exception("[migrate] Error auto-migrating personal_streaks: %s", e)

        # Auto-migrate streak_checkins
        try:
            res = conn.execute(text("PRAGMA table_info(streak_checkins)"))
            cols = [row[1] for row in res.fetchall()]
            if cols:
                checkin_migrations = {
                    "note": "ALTER TABLE streak_checkins ADD COLUMN note TEXT DEFAULT ''",
                    "mood": "ALTER TABLE streak_checkins ADD COLUMN mood INTEGER",
                }
                for col_name, sql in checkin_migrations.items():
                    if col_name not in cols:
                        logger.info("[migrate] Adding column streak_checkins.%s", col_name)
                        conn.execute(text(sql))
        except Exception as e:
            logger.exception("[migrate] Error auto-migrating streak_checkins: %s", e)

        conn.commit()
