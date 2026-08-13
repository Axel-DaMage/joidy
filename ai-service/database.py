import json
import struct
from config import settings
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=3600,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def _vector_literal(embedding: list[float]) -> str:
    """Serialize a Python list into the pgvector text format ``[a,b,c]``.

    ``str(list)`` produces Python repr (``[0.1, 0.2, ...]``) which is fragile
    for pgvector. ``json.dumps`` with tight separators yields the canonical
    pgvector format with no spaces after commas.
    """
    return json.dumps(embedding, separators=(",", ":"))

def store_embedding(note_id: int, embedding: list[float]):
    """Store or update embedding for a note."""
    with engine.connect() as conn:
        conn.execute(
            text("""
            INSERT INTO note_embeddings (note_id, embedding)
            VALUES (:note_id, :embedding)
            ON CONFLICT (note_id) DO UPDATE SET embedding = EXCLUDED.embedding
            """),
            {"note_id": note_id, "embedding": _vector_literal(embedding)}
        )
        conn.execute(
            text("UPDATE notes SET is_embedded = true WHERE id = :note_id"),
            {"note_id": note_id}
        )
        conn.commit()

def find_similar_notes(embedding: list[float], limit: int = 5) -> list[dict]:
    """Find notes with similar embeddings using cosine similarity via pgvector."""
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
            SELECT note_id, embedding <=> :embedding as distance
            FROM note_embeddings
            ORDER BY embedding <=> :embedding ASC
            LIMIT :limit
            """),
            {"embedding": _vector_literal(embedding), "limit": limit}
        ).fetchall()
        return [{"note_id": row[0], "distance": row[1]} for row in rows]
