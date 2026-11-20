"""Tests for POST /plan-suggest (#1237) and the plan_suggest parsing module.

Covers the three acceptance-critical paths: defensive JSON parsing (fenced /
messy output), busy-block overlap filtering, and the graceful no-provider
fallback (never a 5xx when no AI key is configured).
"""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import main
import pytest
from circuit_breaker import CircuitState
from config import settings
from fastapi.testclient import TestClient
from plan_suggest import _extract_json, build_plan_prompt, parse_plan_response

PROVIDER_KEYS = (
    "gemini_api_key",
    "openai_api_key",
    "anthropic_api_key",
    "openrouter_api_key",
    "cohere_api_key",
)

TASKS = [
    {"id": 1, "title": "Write report", "priority": "HIGH", "duration_minutes": 60},
    {"id": 2, "title": "Read chapter", "priority": "LOW", "duration_minutes": None},
]

BUSY = [
    {"start": "2026-03-09T10:00:00", "end": "2026-03-09T11:00:00"},  # Mon 10:00-11:00 local
]

WINDOW = {"week_start": "2026-03-09", "week_end": "2026-03-15", "timezone": "UTC"}


@pytest.fixture
def ai_disabled(monkeypatch):
    """Force `settings.is_llm_configured` to False deterministically."""
    for key in PROVIDER_KEYS:
        monkeypatch.setattr(settings, key, "")
    monkeypatch.setattr(settings, "ollama_base_url", "")
    monkeypatch.setattr(settings, "internal_secret", "")
    monkeypatch.setattr(settings, "llm_model", "gemini:gemini-2.0-flash")
    return settings


@pytest.fixture
def ai_enabled(monkeypatch):
    """Enable the LLM path with a mocked client + limiter."""
    for key in PROVIDER_KEYS:
        monkeypatch.setattr(settings, key, "")
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(settings, "internal_secret", "")
    monkeypatch.setattr(settings, "llm_model", "gemini:gemini-2.0-flash")

    limiter = SimpleNamespace(acquire=AsyncMock())
    monkeypatch.setattr(main, "get_limiter", lambda *a, **k: limiter)
    monkeypatch.setattr(main, "record_usage", MagicMock())

    llm = SimpleNamespace(
        provider_name="fake-llm",
        generate=AsyncMock(return_value='{"suggestions": []}'),
        health_check=AsyncMock(return_value=True),
    )
    monkeypatch.setattr(main, "get_llm_client", lambda: llm)
    return SimpleNamespace(llm=llm, limiter=limiter)


def _client() -> TestClient:
    return TestClient(main.app)


def _payload(**overrides):
    base = {
        "tasks": TASKS,
        "busy_blocks": BUSY,
        "week_start": "2026-03-09",
        "week_end": "2026-03-15",
        "timezone": "UTC",
    }
    base.update(overrides)
    return base


# ── _extract_json ──────────────────────────────────────────────────────


class TestExtractJson(unittest.TestCase):
    def test_clean_object(self):
        assert _extract_json('{"suggestions": []}') == {"suggestions": []}

    def test_strips_json_fence(self):
        raw = '```json\n{"suggestions": [{"task_id": 1}]}\n```'
        assert _extract_json(raw) == {"suggestions": [{"task_id": 1}]}

    def test_strips_bare_fence(self):
        raw = '```\n{"suggestions": []}\n```'
        assert _extract_json(raw) == {"suggestions": []}

    def test_prose_around_object(self):
        raw = 'Sure! Here is the plan:\n{"suggestions": [{"task_id": 2}]}\nHope that helps.'
        assert _extract_json(raw) == {"suggestions": [{"task_id": 2}]}

    def test_bare_array(self):
        assert _extract_json('[{"task_id": 1}]') == [{"task_id": 1}]

    def test_garbage_returns_none(self):
        assert _extract_json("no json at all") is None
        assert _extract_json("") is None
        assert _extract_json("{broken") is None


# ── parse_plan_response validation ─────────────────────────────────────


class TestParsePlanResponse(unittest.TestCase):
    def _parse(self, suggestions_json, **kw):
        raw = json.dumps({"suggestions": suggestions_json})
        return parse_plan_response(
            raw,
            kw.get("tasks", TASKS),
            kw.get("busy_blocks", BUSY),
            kw.get("week_start", WINDOW["week_start"]),
            kw.get("week_end", WINDOW["week_end"]),
            kw.get("timezone", WINDOW["timezone"]),
        )

    def test_valid_suggestion_accepted(self):
        out = self._parse(
            [{"task_id": 1, "date": "2026-03-09", "start_time": "12:00", "end_time": "13:00", "rationale": "free"}]
        )
        assert out == [
            {"task_id": 1, "date": "2026-03-09", "start_time": "12:00", "end_time": "13:00", "rationale": "free"}
        ]

    def test_overlap_with_busy_block_dropped(self):
        # Busy: 10:00-11:00. 10:30-11:30 overlaps → dropped. 11:00-12:00 is fine.
        out = self._parse(
            [
                {"task_id": 1, "date": "2026-03-09", "start_time": "10:30", "end_time": "11:30"},
                {"task_id": 2, "date": "2026-03-09", "start_time": "11:00", "end_time": "11:30"},
            ]
        )
        assert [s["task_id"] for s in out] == [2]

    def test_overlap_boundary_touching_is_allowed(self):
        # Ends exactly when the busy block starts → no overlap.
        out = self._parse([{"task_id": 1, "date": "2026-03-09", "start_time": "09:00", "end_time": "10:00"}])
        assert len(out) == 1

    def test_unknown_task_id_dropped(self):
        out = self._parse([{"task_id": 99, "date": "2026-03-10", "start_time": "09:00"}])
        assert out == []

    def test_duplicate_task_id_keeps_first(self):
        out = self._parse(
            [
                {"task_id": 1, "date": "2026-03-09", "start_time": "08:00", "end_time": "09:00"},
                {"task_id": 1, "date": "2026-03-10", "start_time": "08:00", "end_time": "09:00"},
            ]
        )
        assert len(out) == 1
        assert out[0]["date"] == "2026-03-09"

    def test_outside_window_dropped(self):
        out = self._parse(
            [
                {"task_id": 1, "date": "2026-03-08", "start_time": "09:00"},  # before window
                {"task_id": 2, "date": "2026-03-16", "start_time": "09:00"},  # after window
            ]
        )
        assert out == []

    def test_end_before_start_dropped(self):
        out = self._parse([{"task_id": 1, "date": "2026-03-09", "start_time": "14:00", "end_time": "13:00"}])
        assert out == []

    def test_missing_end_time_uses_default_duration(self):
        # Task 2 has no duration → 30min default. 10:45 + 30min overlaps the
        # 10:00-11:00 busy block → dropped; 12:00 + 30min is clean.
        out = self._parse(
            [
                {"task_id": 2, "date": "2026-03-09", "start_time": "10:45"},
                {"task_id": 2, "date": "2026-03-09", "start_time": "12:00"},
            ]
        )
        assert len(out) == 1
        assert out[0]["start_time"] == "12:00"
        assert out[0]["end_time"] == "12:30"

    def test_suggestions_do_not_overlap_each_other(self):
        out = self._parse(
            [
                {"task_id": 1, "date": "2026-03-09", "start_time": "12:00", "end_time": "13:00"},
                {"task_id": 2, "date": "2026-03-09", "start_time": "12:30", "end_time": "13:30"},
            ]
        )
        assert [s["task_id"] for s in out] == [1]

    def test_malformed_fields_dropped(self):
        out = self._parse(
            [
                {"task_id": "one", "date": "2026-03-09", "start_time": "08:00"},
                {"task_id": 1, "date": "not-a-date", "start_time": "08:00"},
                {"task_id": 2, "date": "2026-03-09", "start_time": "25:00"},
                "not-a-dict",
            ]
        )
        assert out == []

    def test_aware_busy_blocks_compare_correctly(self):
        # Busy block sent with an explicit offset; 14:00Z == 10:00-04:00.
        busy = [{"start": "2026-03-09T10:00:00-04:00", "end": "2026-03-09T11:00:00-04:00"}]
        out = self._parse(
            [{"task_id": 1, "date": "2026-03-09", "start_time": "14:30", "end_time": "15:00"}],
            busy_blocks=busy,
        )
        assert out == []

    def test_non_json_returns_empty(self):
        assert parse_plan_response("I cannot help with that", TASKS, BUSY, **WINDOW) == []

    def test_bad_window_returns_empty(self):
        assert parse_plan_response('{"suggestions": []}', TASKS, BUSY, "nope", "nope", "UTC") == []


# ── build_plan_prompt ──────────────────────────────────────────────────


class TestBuildPlanPrompt(unittest.TestCase):
    def test_prompt_includes_tasks_busy_and_window(self):
        prompt = build_plan_prompt(TASKS, BUSY, "2026-03-09", "2026-03-15", "America/Santiago")
        assert "America/Santiago" in prompt
        assert "2026-03-09" in prompt and "2026-03-15" in prompt
        assert "id=1" in prompt and "Write report" in prompt
        assert "duration=60min" in prompt
        # Task 2 lacks duration → default 30 shown.
        assert "duration=30min" in prompt
        assert "2026-03-09T10:00:00 -> 2026-03-09T11:00:00" in prompt
        assert "STRICT JSON" in prompt

    def test_empty_lists_render_placeholders(self):
        prompt = build_plan_prompt([], [], "2026-03-09", "2026-03-15", "UTC")
        assert "(none" in prompt

    def test_context_hint_included_when_given(self):
        prompt = build_plan_prompt(TASKS, [], "2026-03-09", "2026-03-15", "UTC", context_hint="Mornings only")
        assert "Mornings only" in prompt


# ── POST /plan-suggest endpoint ────────────────────────────────────────


class TestPlanSuggestEndpoint:
    def test_no_provider_returns_graceful_fallback(self, ai_disabled):
        resp = _client().post("/plan-suggest", json=_payload())
        assert resp.status_code == 200
        body = resp.json()
        assert body == {"suggestions": [], "available": False, "reason": "no_provider"}

    def test_success_parses_and_validates(self, ai_enabled):
        ai_enabled.llm.generate = AsyncMock(
            return_value=(
                "```json\n"
                '{"suggestions": ['
                '{"task_id": 1, "date": "2026-03-09", "start_time": "10:30", "end_time": "11:30"},'
                '{"task_id": 2, "date": "2026-03-09", "start_time": "12:00", "end_time": "12:30", '
                '"rationale": "quiet slot"},'
                '{"task_id": 77, "date": "2026-03-09", "start_time": "13:00"}'
                "]}\n```"
            )
        )
        resp = _client().post("/plan-suggest", json=_payload())
        assert resp.status_code == 200
        body = resp.json()
        assert body["available"] is True
        assert body["provider"] == "fake-llm"
        # task 1 overlaps the busy block, task 77 is unknown → only task 2 survives.
        assert body["suggestions"] == [
            {
                "task_id": 2,
                "date": "2026-03-09",
                "start_time": "12:00",
                "end_time": "12:30",
                "rationale": "quiet slot",
            }
        ]

    def test_provider_failure_returns_unavailable_not_500(self, ai_enabled):
        ai_enabled.llm.generate = AsyncMock(side_effect=RuntimeError("provider down"))
        resp = _client().post("/plan-suggest", json=_payload())
        assert resp.status_code == 200
        body = resp.json()
        assert body["available"] is False
        assert body["reason"] == "provider_error"

    def test_circuit_open_returns_graceful(self, ai_enabled):
        import time

        main.llm_circuit_breaker.state = CircuitState.OPEN
        main.llm_circuit_breaker.last_failure_time = time.time()
        resp = _client().post("/plan-suggest", json=_payload())
        assert resp.status_code == 200
        assert resp.json()["reason"] == "circuit_open"
        ai_enabled.llm.generate.assert_not_awaited()

    def test_empty_tasks_short_circuits(self, ai_enabled):
        resp = _client().post("/plan-suggest", json=_payload(tasks=[]))
        assert resp.status_code == 200
        body = resp.json()
        assert body["available"] is True
        assert body["suggestions"] == []
        ai_enabled.llm.generate.assert_not_awaited()

    def test_get_client_raise_returns_no_provider(self, ai_enabled, monkeypatch):
        monkeypatch.setattr(
            main, "get_llm_client", MagicMock(side_effect=ValueError("Provider 'gemini' not configured"))
        )
        resp = _client().post("/plan-suggest", json=_payload())
        assert resp.status_code == 200
        assert resp.json()["reason"] == "no_provider"

    def test_invalid_payload_returns_422(self, ai_disabled):
        resp = _client().post("/plan-suggest", json={"tasks": "not-a-list"})
        assert resp.status_code == 422


if __name__ == "__main__":
    unittest.main()
