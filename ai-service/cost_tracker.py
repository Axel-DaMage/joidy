"""
Tracks approximate Gemini API usage for transparency.
Gemini 2.0 Flash: $0.075/1M input tokens, $0.30/1M output tokens.
text-embedding-004: Free tier.
"""

import sqlite3
from datetime import date
from pathlib import Path

DB_PATH = Path("/data/db/joidy.db")

COST_PER_1M_INPUT = 0.075
COST_PER_1M_OUTPUT = 0.300


def _get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS api_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operation TEXT NOT NULL,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    return conn


def record_usage(operation: str, input_tokens: int = 0, output_tokens: int = 0):
    try:
        conn = _get_conn()
        conn.execute(
            "INSERT INTO api_usage (operation, input_tokens, output_tokens) VALUES (?, ?, ?)",
            (operation, input_tokens, output_tokens),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass  # Non-blocking


def get_monthly_stats() -> dict:
    try:
        conn = _get_conn()
        month_start = date.today().replace(day=1).isoformat()
        row = conn.execute(
            "SELECT SUM(input_tokens), SUM(output_tokens), COUNT(*) FROM api_usage WHERE created_at >= ?",
            (month_start,),
        ).fetchone()
        conn.close()

        total_input = row[0] or 0
        total_output = row[1] or 0
        total_calls = row[2] or 0
        estimated_cost = (total_input / 1_000_000 * COST_PER_1M_INPUT) + (total_output / 1_000_000 * COST_PER_1M_OUTPUT)

        return {
            "month": date.today().strftime("%Y-%m"),
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_api_calls": total_calls,
            "estimated_cost_usd": round(estimated_cost, 4),
        }
    except Exception:
        return {}
