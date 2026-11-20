"""joidy streaks new/checkin/uncheckin/freeze/history."""

import httpx

from tests.conftest import combined, last_body, output_json

STREAK = {"id": 3, "name": "Meditate", "current_streak": 5, "today_checked": False}


def test_streaks_new(invoke, api):
    api.respond["fn"] = lambda req: httpx.Response(201, json=STREAK)
    result = invoke("streaks", "new", "--name", "Meditate", "--category", "salud")
    assert result.exit_code == 0, combined(result)
    assert api.records[-1].url.path == "/personal-streaks/"
    body = last_body(api)
    assert body["name"] == "Meditate"
    assert body["category"] == "salud"
    assert body["frequency"] == "daily"


def test_streaks_new_every_n(invoke, api):
    api.respond["fn"] = lambda req: httpx.Response(201, json=STREAK)
    result = invoke("streaks", "new", "--name", "Gym", "--frequency", "every_n", "--frequency-days", "2")
    assert result.exit_code == 0
    assert last_body(api)["frequency_days"] == 2


def test_streaks_new_invalid_frequency(invoke, api):
    result = invoke("streaks", "new", "--name", "x", "--frequency", "hourly")
    assert result.exit_code == 2


def test_streaks_ls(invoke, api):
    api.respond["fn"] = lambda req: httpx.Response(200, json=[STREAK])
    result = invoke("streaks", "ls", "--archived")
    assert result.exit_code == 0
    assert api.records[-1].url.params["include_archived"] == "true"
    assert output_json(result)[0]["id"] == 3


def test_streaks_checkin(invoke, api):
    api.respond["fn"] = lambda req: httpx.Response(200, json={**STREAK, "today_checked": True, "current_streak": 6})
    result = invoke("streaks", "checkin", "3")
    assert result.exit_code == 0
    assert api.records[-1].method == "POST"
    assert api.records[-1].url.path == "/personal-streaks/3/checkin"
    assert output_json(result)["current_streak"] == 6


def test_streaks_checkin_full_body(invoke, api):
    api.respond["fn"] = lambda req: httpx.Response(200, json=STREAK)
    result = invoke("streaks", "checkin", "3", "--note", "felt great", "--mood", "4", "--date", "2026-01-10")
    assert result.exit_code == 0
    body = last_body(api)
    assert body == {"note": "felt great", "mood": 4, "check_date": "2026-01-10"}


def test_streaks_uncheckin(invoke, api):
    api.respond["fn"] = lambda req: httpx.Response(200, json=STREAK)
    result = invoke("streaks", "uncheckin", "3")
    assert result.exit_code == 0
    assert api.records[-1].method == "DELETE"
    assert api.records[-1].url.path == "/personal-streaks/3/checkin"


def test_streaks_freeze(invoke, api):
    api.respond["fn"] = lambda req: httpx.Response(200, json={**STREAK, "freeze_used": 1})
    result = invoke("streaks", "freeze", "3")
    assert result.exit_code == 0
    assert api.records[-1].url.path == "/personal-streaks/3/freeze"


def test_streaks_freeze_none_available(invoke, api):
    api.respond["fn"] = lambda req: httpx.Response(400, json={"detail": "No freezes available"})
    result = invoke("streaks", "freeze", "3")
    assert result.exit_code == 2


def test_streaks_history(invoke, api):
    hist = [{"date": "2026-01-10", "note": "", "mood": 4, "created_at": None}]
    api.respond["fn"] = lambda req: httpx.Response(200, json=hist)
    result = invoke("streaks", "history", "3", "--days", "30")
    assert result.exit_code == 0
    assert api.records[-1].url.params["days"] == "30"
    assert output_json(result) == hist


def test_streaks_rm_requires_yes(invoke, api):
    result = invoke("streaks", "rm", "3")
    assert result.exit_code == 2
    assert api.records == []
