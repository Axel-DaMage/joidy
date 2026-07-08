import struct

import sqlite_vec
from config import settings
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker


def _setup_sqlite(dbapi_connection, connection_record):
    dbapi_connection.enable_load_extension(True)
    sqlite_vec.load(dbapi_connection)
    dbapi_connection.enable_load_extension(False)
    dbapi_connection.execute("PRAGMA journal_mode=WAL")
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
)
event.listen(engine, "connect", _setup_sqlite)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def store_embedding(note_id: int, embedding: list[float]):
    """Store or update embedding for a note."""
    blob = struct.pack(f"{len(embedding)}f", *embedding)
    with engine.connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO note_embeddings (note_id, embedding) VALUES (?, ?)",  # type: ignore
            (note_id, blob),
        )
        conn.execute(
            "UPDATE notes SET is_embedded = 1 WHERE id = ?",  # type: ignore
            (note_id,),
        )
        conn.commit()


def find_similar_notes(embedding: list[float], limit: int = 5) -> list[dict]:
    """Find notes with similar embeddings using cosine similarity via sqlite-vec."""
    blob = struct.pack(f"{len(embedding)}f", *embedding)
    with engine.connect() as conn:
        rows = conn.execute(  # type: ignore
            """
            SELECT note_id, vec_distance_cosine(embedding, ?) as distance
            FROM note_embeddings
            ORDER BY distance ASC
            LIMIT ?
            """,
            (blob, limit),
        ).fetchall()
        return [{"note_id": row[0], "distance": row[1]} for row in rows]
