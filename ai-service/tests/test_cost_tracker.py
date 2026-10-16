"""Unit tests for cost_tracker accounting (engine fully mocked)."""

import unittest
from unittest.mock import MagicMock, patch

import cost_tracker
from cost_tracker import COST_PER_1M_INPUT, COST_PER_1M_OUTPUT, get_monthly_stats, record_usage


def _mock_engine(fetchone_row=None, side_effect=None):
    """Build a MagicMock engine whose connect() yields a usable conn."""
    engine = MagicMock()
    if side_effect is not None:
        engine.connect.side_effect = side_effect
        return engine
    conn = MagicMock()
    engine.connect.return_value.__enter__.return_value = conn
    if fetchone_row is not None:
        conn.execute.return_value.fetchone.return_value = fetchone_row
    return engine


class TestRecordUsage(unittest.TestCase):
    def test_inserts_usage_row_and_commits(self):
        engine = _mock_engine()
        with patch.object(cost_tracker, "engine", engine):
            record_usage("embed", input_tokens=120, output_tokens=0)

        conn = engine.connect.return_value.__enter__.return_value
        conn.execute.assert_called_once()
        params = conn.execute.call_args[0][1]
        self.assertEqual(params, {"op": "embed", "in": 120, "out": 0})
        conn.commit.assert_called_once()

    def test_db_failure_is_swallowed(self):
        """record_usage must never break the actual AI request."""
        engine = _mock_engine(side_effect=RuntimeError("db down"))
        with patch.object(cost_tracker, "engine", engine):
            record_usage("classify", input_tokens=10)  # must not raise


class TestGetMonthlyStats(unittest.TestCase):
    def test_aggregates_tokens_and_cost(self):
        engine = _mock_engine(fetchone_row=(1_000_000, 500_000, 42))
        with patch.object(cost_tracker, "engine", engine):
            stats = get_monthly_stats()

        self.assertEqual(stats["total_input_tokens"], 1_000_000)
        self.assertEqual(stats["total_output_tokens"], 500_000)
        self.assertEqual(stats["total_api_calls"], 42)
        expected = 1.0 * COST_PER_1M_INPUT + 0.5 * COST_PER_1M_OUTPUT
        self.assertAlmostEqual(stats["estimated_cost_usd"], round(expected, 4))

    def test_zero_usage_returns_zero_cost(self):
        engine = _mock_engine(fetchone_row=(0, 0, 0))
        with patch.object(cost_tracker, "engine", engine):
            stats = get_monthly_stats()
        self.assertEqual(stats["estimated_cost_usd"], 0)

    def test_db_failure_returns_zeroed_stats(self):
        engine = _mock_engine(side_effect=RuntimeError("db down"))
        with patch.object(cost_tracker, "engine", engine):
            stats = get_monthly_stats()
        self.assertEqual(stats["total_api_calls"], 0)
        self.assertEqual(stats["estimated_cost_usd"], 0)


if __name__ == "__main__":
    unittest.main()
