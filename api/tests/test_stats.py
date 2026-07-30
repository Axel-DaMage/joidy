"""Tests for the /stats router."""

from datetime import datetime, timezone

from models.gamification import UserStats, XPEvent
from models.goal import Goal, GoalFailConfig, GoalMeasurement, GoalState, GoalTemporality
from models.note import Note


def test_get_system_stats(client, db_session):
    db_session.add(Note(title="Note 1", content="", source="joidy"))
    db_session.add(Goal(
        title="Goal 1",
        target_value=1,
        current_value=0,
        temporality=GoalTemporality.DAILY,
        measurement_type=GoalMeasurement.COUNT,
        state=GoalState.ACTIVE,
        fail_config=GoalFailConfig.STATIC,
    ))
    db_session.add(UserStats(total_xp=100, current_streak=5, longest_streak=5, plant_stage=0))
    db_session.add(XPEvent(event_type="note_created", xp=10, metadata_json='{}'))
    db_session.commit()

    resp = client.get("/stats/system")
    assert resp.status_code == 200
    data = resp.json()
    assert data["notes"] == 1
    assert data["goals"] == 1
    assert data["total_xp"] == 100
    assert data["current_streak"] == 5


def test_get_activity_stats(client, db_session):
    now = datetime.now(timezone.utc)
    db_session.add(Note(title="Recent", content="", created_at=now, source="joidy"))
    db_session.add(XPEvent(event_type="note_created", xp=10, created_at=now, metadata_json='{}'))
    db_session.commit()

    resp = client.get("/stats/activity?days=7")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["days"]) == 7
    today = data["days"][0]
    assert today["notes_created"] == 1
    assert today["xp_events"] == 1
