"""
Tracks approximate AI provider usage for transparency.

Costs are rough estimates based on Gemini 2.0 Flash pricing:
$0.075/1M input tokens, $0.30/1M output tokens.
text-embedding-004: free tier (no input cost).

Records are stored in the shared PostgreSQL database (table ``api_usage``)
created by Alembic migration. Previously this used a stale SQLite file at
``/data/db/joidy.db`` which never worked after the PostgreSQL migration (#273).
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import text

from database import engine

logger = logging.getLogger(__name__)

COST_PER_1M_INPUT = 0.075
COST_PER_1M_OUTPUT = 0.300


def record_usage(operation: str, input_tokens: int = 0, output_tokens: int = 0):
    """Persist a single API call's token usage.

    Non-blocking: logs a warning on failure instead of raising, so a tracking
    issue never breaks the actual AI request. Unlike the previous SQLite
    implementation, errors are surfaced in the logs rather than silently
    swallowed.
    """
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "INSERT INTO api_usage (operation, input_tokens, output_tokens) "
                    "VALUES (:op, :in, :out)"
                ),
                {"op": operation, "in": input_tokens, "out": output_tokens},
            )
            conn.commit()
    except Exception as exc:
        logger.warning("[cost_tracker] record_usage failed: %s", exc)


def get_monthly_stats() -> dict:
    """Aggregate token usage and estimated cost for the current month."""
    try:
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT COALESCE(SUM(input_tokens), 0), "
                    "COALESCE(SUM(output_tokens), 0), COUNT(*) "
                    "FROM api_usage WHERE created_at >= :month_start"
                ),
                {"month_start": month_start},
            ).fetchone()

        total_input = int(row[0] or 0)
        total_output = int(row[1] or 0)
        total_calls = int(row[2] or 0)
        estimated_cost = (
            total_input / 1_000_000 * COST_PER_1M_INPUT
            + total_output / 1_000_000 * COST_PER_1M_OUTPUT
        )

        return {
            "month": now.strftime("%Y-%m"),
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_api_calls": total_calls,
            "estimated_cost_usd": round(estimated_cost, 4),
        }
    except Exception as exc:
        logger.warning("[cost_tracker] get_monthly_stats failed: %s", exc)
        return {
            "month": datetime.now(timezone.utc).strftime("%Y-%m"),
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_api_calls": 0,
            "estimated_cost_usd": 0,
        }
