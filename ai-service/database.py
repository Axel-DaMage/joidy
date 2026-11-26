import json

from config import settings
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

# Pool sizing (#1584): since #1533 every psycopg2 call runs on a worker
# thread via ``asyncio.to_thread``, so the pool — not the event loop — is
# the concurrency ceiling. Each DB call site holds a single connection and
# the calls are sequential within a request, so demand ≈ concurrent
# in-flight requests: 10 steady-state connections cover normal load and 10
# overflow absorb /embed bursts during vault sync. A dedicated
# ThreadPoolExecutor sized to the pool was rejected: ``to_thread`` always
# uses the default executor (extra workers simply queue on pool checkout,
# which degrades gracefully) so it would add ``run_in_executor`` plumbing
# at every call site for no throughput gain in a single-user app.
#
# The sizing kwargs are QueuePool-specific — the SQLite engines used by the
# test suite (SingletonThreadPool/StaticPool) reject them, so they only
# apply to real Postgres URLs.
_pool_kwargs = (
    {"pool_size": 10, "max_overflow": 10} if make_url(settings.database_url).get_backend_name() != "sqlite" else {}
)
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=3600,
    **_pool_kwargs,
)


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
            {"note_id": note_id, "embedding": _vector_literal(embedding)},
        )
        conn.execute(text("UPDATE notes SET is_embedded = true WHERE id = :note_id"), {"note_id": note_id})
        conn.commit()


def find_similar_note_chunks(embedding: list[float], limit: int, snippet_chars: int) -> list[dict]:
    """Return ``note_id``/``title``/``snippet`` for the closest embeddings — one query.

    The JOIN against ``notes`` fetches the display payload in the same
    round-trip instead of a second per-id lookup (#1541 N+1), and
    ``left(content, :snippet_chars)`` truncates server-side so full note
    bodies never cross the wire. The distance is computed once in ORDER BY —
    the previous version also SELECTed it although no caller used it.
    Embeddings pointing at deleted notes are excluded by the JOIN.
    """
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
            SELECT n.id, n.title, left(n.content, :snippet_chars) AS snippet
            FROM note_embeddings ne
            JOIN notes n ON n.id = ne.note_id
            ORDER BY ne.embedding <=> :embedding ASC
            LIMIT :limit
            """),
            {
                "embedding": _vector_literal(embedding),
                "snippet_chars": snippet_chars,
                "limit": limit,
            },
        ).fetchall()
        return [{"note_id": row[0], "title": row[1], "snippet": row[2] or ""} for row in rows]
