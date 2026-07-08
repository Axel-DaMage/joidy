import struct
from config import settings
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

engine = create_engine(
    settings.database_url,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def store_embedding(note_id: int, embedding: list[float]):
    """Store or update embedding for a note."""
    with engine.connect() as conn:
        conn.execute(
            text("""
            INSERT INTO note_embeddings (note_id, embedding)
            VALUES (:note_id, :embedding)
            ON CONFLICT (note_id) DO UPDATE SET embedding = EXCLUDED.embedding
            """),
            {"note_id": note_id, "embedding": str(embedding)}
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
            {"embedding": str(embedding), "limit": limit}
        ).fetchall()
        return [{"note_id": row[0], "distance": row[1]} for row in rows]
