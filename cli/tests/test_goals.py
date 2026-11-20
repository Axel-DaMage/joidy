"""joidy goals — including per-period instance completion."""

import httpx

from tests.conftest import combined, last_body, output_json

GOAL = {"id": 7, "title": "Ship it", "state": "ACTIVE", "temporality": "DAILY"}


def test_goals_new_oneoff(invoke, api):
    api.respond["fn"] = lambda req: httpx.Response(201, json=GOAL)
    result = invoke("goals", "new", "--title", "Ship it")
    assert result.exit_code == 0, combined(result)
    body = last_body(api)
    assert api.records[-1].url.path == "/goals/"
    assert body["title"] == "Ship it"
    assert body["temporality"] == "ONEOFF"
    assert body["measurement_type"] == "COUNT"


def test_goals_new_temporality_instance(invoke, api):
    api.respond["fn"] = lambda req: httpx.Response(201, json=GOAL)
    result = invoke(
        "goals",
        "new",
        "--title",
        "Read",
        "--temporality",
        "daily",
        "--target",
        "30",
        "--fail-config",
        "snowball",
        "--priority",
        "5",
    )
    assert result.exit_code == 0
    body = last_body(api)
    assert body["temporality"] == "DAILY"
    assert body["target_value"] == 30.0
    assert body["fail_config"] == "SNOWBALL"
    assert body["priority"] == 5


def test_goals_new_invalid_temporality(invoke, api):
    result = invoke("goals", "new", "--title", "x", "--temporality", "hourly")
    assert result.exit_code == 2
    assert api.records == []


def test_goals_ls_state_filter(invoke, api):
    api.respond["fn"] = lambda req: httpx.Response(200, json=[GOAL])
    result = invoke("goals", "ls", "--state", "active")
    assert result.exit_code == 0
    assert api.records[-1].url.params["state"] == "ACTIVE"


def test_goals_done(invoke, api):
    # AC: per-period instance completion — POST /goals/{id}/complete.
    payload = {"goal": {**GOAL, "state": "COMPLETED", "is_completed": True}, "gamification": {"xp_awarded": 50}}
    api.respond["fn"] = lambda req: httpx.Response(200, json=payload)
    result = invoke("goals", "done", "7")
    assert result.exit_code == 0
    assert api.records[-1].method == "POST"
    assert api.records[-1].url.path == "/goals/7/complete"
    data = output_json(result)
    assert data["goal"]["id"] == 7


def test_goals_done_already_completed(invoke, api):
    payload = {"goal": GOAL, "gamification": {}, "already_completed": True}
    api.respond["fn"] = lambda req: httpx.Response(200, json=payload)
    result = invoke("goals", "done", "7", "--jq", "already_completed")
    assert result.exit_code == 0
    assert output_json(result) is True


def test_goals_fail(invoke, api):
    api.respond["fn"] = lambda req: httpx.Response(200, json={**GOAL, "state": "FAILED"})
    result = invoke("goals", "fail", "7")
    assert result.exit_code == 0
    assert api.records[-1].url.path == "/goals/7/fail"


def test_goals_rm_requires_yes(invoke, api):
    result = invoke("goals", "rm", "7")
    assert result.exit_code == 2
    assert api.records == []
