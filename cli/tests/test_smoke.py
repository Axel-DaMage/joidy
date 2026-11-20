"""End-to-end smoke test against a live Joidy API.

Skipped by default. Enable by pointing at a running stack:

    JOIDY_SMOKE_API_URL=http://localhost:8000 JOIDY_SMOKE_PASSWORD=<pw> \\
        pytest cli/tests/test_smoke.py -v

Covers the AC smoke surface: ``auth login`` → ``notes new`` →
``streaks new`` → ``streaks checkin``, then cleans up.
"""

import os

import pytest
from joidy_cli.main import app
from typer.testing import CliRunner

API_URL = os.environ.get("JOIDY_SMOKE_API_URL")
PASSWORD = os.environ.get("JOIDY_SMOKE_PASSWORD", "")

pytestmark = pytest.mark.skipif(not API_URL, reason="set JOIDY_SMOKE_API_URL to run the live smoke test")


def _parse(result):
    import json

    return json.loads(result.output)


def test_smoke_notes_and_streaks(tmp_path, monkeypatch):
    monkeypatch.setenv("JOIDY_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("JOIDY_API_URL", API_URL)
    for var in ("JOIDY_TOKEN",):
        monkeypatch.delenv(var, raising=False)
    runner = CliRunner()

    # auth login (skipped silently if the instance has no auth password)
    login = runner.invoke(app, ["auth", "login", "--password", PASSWORD])
    assert login.exit_code in (0, 3), login.output

    # notes new
    note = runner.invoke(app, ["notes", "new", "--title", "joidy-cli-smoke", "--content", "smoke", "--yes"])
    assert note.exit_code == 0, note.output
    note_id = _parse(note)["id"]

    # streaks new + checkin
    streak = runner.invoke(app, ["streaks", "new", "--name", "joidy-cli-smoke"])
    assert streak.exit_code == 0, streak.output
    streak_id = _parse(streak)["id"]

    checkin = runner.invoke(app, ["streaks", "checkin", str(streak_id), "--note", "smoke"])
    assert checkin.exit_code == 0, checkin.output

    # cleanup
    assert runner.invoke(app, ["streaks", "rm", str(streak_id), "--yes"]).exit_code == 0
    assert runner.invoke(app, ["notes", "rm", str(note_id), "--yes"]).exit_code == 0
