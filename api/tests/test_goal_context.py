"""Tests for GoalContext, INBOX state, execution-queue endpoint and vault round-trip (#1198, #1199)."""

from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from models.goal import Goal, GoalContext, GoalState
from services import joidy_vault_writer
from sqlalchemy.orm import Session


def test_create_inbox_goal_with_context(client: TestClient):
    response = client.post(
        "/goals/",
        json={
            "title": "Idea rápida de noche",
            "state": "INBOX",
            "context": "NIGHT",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["state"] == "INBOX"
    assert data["context"] == "NIGHT"

    # Query via state filter
    list_res = client.get("/goals/?state=INBOX")
    assert list_res.status_code == 200
    items = list_res.json()
    assert any(g["id"] == data["id"] for g in items)

    # Query via context filter
    ctx_res = client.get("/goals/?context=NIGHT")
    assert ctx_res.status_code == 200
    ctx_items = ctx_res.json()
    assert any(g["id"] == data["id"] for g in ctx_items)


def test_triage_inbox_goal_to_active(client: TestClient):
    create_res = client.post(
        "/goals/",
        json={"title": "Tarea pendiente de clasificar", "state": "INBOX"},
    )
    goal_id = create_res.json()["id"]

    patch_res = client.put(
        f"/goals/{goal_id}",
        json={
            "state": "ACTIVE",
            "context": "MORNING",
            "priority": 5,
        },
    )
    assert patch_res.status_code == 200
    updated = patch_res.json()
    assert updated["state"] == "ACTIVE"
    assert updated["context"] == "MORNING"
    assert updated["priority"] == 5


def test_route_order_does_not_conflict_with_get_goal(client: TestClient):
    res = client.get("/goals/execution-queue")
    assert res.status_code == 200
    body = res.json()
    assert "context" in body
    assert "items" in body
    assert "generated_at" in body


def test_queue_auto_resolution_morning(client: TestClient):
    # Mock time at 10:00 AM (local hour < 15)
    fake_morning = datetime(2026, 11, 19, 10, 30, tzinfo=ZoneInfo("UTC"))
    with patch("routers.goals.get_local_now", return_value=fake_morning):
        res = client.get("/goals/execution-queue?context=auto")
        assert res.status_code == 200
        assert res.json()["context"] == "MORNING"


def test_queue_auto_resolution_night(client: TestClient):
    # Mock time at 17:00 PM (local hour >= 15)
    fake_night = datetime(2026, 11, 19, 17, 30, tzinfo=ZoneInfo("UTC"))
    with patch("routers.goals.get_local_now", return_value=fake_night):
        res = client.get("/goals/execution-queue?context=auto")
        assert res.status_code == 200
        assert res.json()["context"] == "NIGHT"


def test_queue_filtering_and_priority_ordering(client: TestClient, db_session: Session):
    g_morning = Goal(
        title="Rutina matutina",
        state=GoalState.ACTIVE,
        context=GoalContext.MORNING,
        priority=2,
        is_completed=False,
    )
    g_night = Goal(
        title="Deep work nocturno",
        state=GoalState.ACTIVE,
        context=GoalContext.NIGHT,
        priority=10,
        is_completed=False,
    )
    g_any_low = Goal(
        title="Tarea comodín baja",
        state=GoalState.ACTIVE,
        context=GoalContext.ANY,
        priority=1,
        is_completed=False,
    )
    g_any_high = Goal(
        title="Tarea comodín alta",
        state=GoalState.ACTIVE,
        context=GoalContext.ANY,
        priority=8,
        is_completed=False,
    )
    g_inbox = Goal(
        title="Sin triar",
        state=GoalState.INBOX,
        context=GoalContext.MORNING,
        priority=9,
        is_completed=False,
    )
    g_completed = Goal(
        title="Ya completada",
        state=GoalState.COMPLETED,
        context=GoalContext.MORNING,
        priority=9,
        is_completed=True,
    )
    g_paused = Goal(
        title="Pausada",
        state=GoalState.PAUSED,
        context=GoalContext.MORNING,
        priority=9,
        is_completed=False,
    )

    db_session.add_all([g_morning, g_night, g_any_low, g_any_high, g_inbox, g_completed, g_paused])
    db_session.commit()

    res = client.get("/goals/execution-queue?context=morning")
    assert res.status_code == 200
    items = res.json()["items"]
    titles = [i["title"] for i in items]

    # Morning queue should include MORNING and ANY, ordered by priority DESC (8 -> 2 -> 1)
    assert titles == ["Tarea comodín alta", "Rutina matutina", "Tarea comodín baja"]
    # NIGHT, INBOX, COMPLETED, PAUSED must not be included
    assert "Deep work nocturno" not in titles
    assert "Sin triar" not in titles
    assert "Ya completada" not in titles
    assert "Pausada" not in titles


def test_vault_restore_preserves_context_and_defaults_legacy(db_session: Session):
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir)
        obj_dir = vault_path / "Objetivos"
        obj_dir.mkdir(parents=True)

        with patch("services.joidy_vault_writer.get_objectives_dir", return_value=obj_dir):
            goal_with_ctx = Goal(
                id=999101,
                title="Meta con contexto",
                description="Contenido",
                context=GoalContext.NIGHT,
                state=GoalState.ACTIVE,
            )
            joidy_vault_writer._write_goal_file(db_session, goal_with_ctx, obj_dir)

            legacy_file = obj_dir / "999102_legacy.md"
            legacy_file.write_text(
                """---
goal_id: 999102
joidy_managed: true
state: ACTIVE
---
# Legacy Goal
""",
                encoding="utf-8",
            )

            # Delete these 2 if present to test restore
            db_session.query(Goal).filter(Goal.id.in_([999101, 999102])).delete()
            db_session.commit()

            res = joidy_vault_writer.restore_goals_from_vault(db_session)
            assert res["restored"] >= 2

            restored_101 = db_session.query(Goal).filter(Goal.id == 999101).one()
            assert restored_101.context == GoalContext.NIGHT

            restored_102 = db_session.query(Goal).filter(Goal.id == 999102).one()
            assert restored_102.context == GoalContext.ANY
