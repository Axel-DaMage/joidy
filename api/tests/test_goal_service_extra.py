"""Extra coverage for ``services/goal_service.py`` (#1401).

Targets the branches existing goal tests miss: parent-hierarchy
validation, temporality/fail-config parsing, note→goal sync (create,
update, pending_removal), progress helpers, expiry evaluation across
fail configs, and streak computation. DB state is asserted directly.
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from models.goal import Goal, GoalFailConfig, GoalMeasurement, GoalState, GoalTemporality
from models.note import Note, NoteTag, Tag
from services import goal_service as svc
from services.timezone_utils import get_local_today


def _goal(db, **kwargs) -> Goal:
    goal = Goal(title=kwargs.pop("title", "goal"), **kwargs)
    db.add(goal)
    db.flush()
    return goal


def _note(db, content="body", **kwargs) -> Note:
    note = Note(title=kwargs.pop("title", "n"), content=content, source="joidy", **kwargs)
    db.add(note)
    db.flush()
    return note


# ─── validate_goal_parent ─────────────────────────────────────────────────────


def test_validate_parent_none_and_valid(db_session):
    svc.validate_goal_parent(db_session, goal_id=None, parent_id=None)
    parent = _goal(db_session, title="parent")
    child = _goal(db_session, title="child")
    svc.validate_goal_parent(db_session, goal_id=child.id, parent_id=parent.id)


def test_validate_parent_self_cycle_missing(db_session):
    goal = _goal(db_session)
    with pytest.raises(HTTPException) as exc:
        svc.validate_goal_parent(db_session, goal_id=goal.id, parent_id=goal.id)
    assert exc.value.status_code == 400

    # Cycle: a → b → a
    a = _goal(db_session, title="a")
    b = _goal(db_session, title="b", parent_id=a.id)
    a.parent_id = b.id
    db_session.flush()
    with pytest.raises(HTTPException) as exc:
        svc.validate_goal_parent(db_session, goal_id=a.id, parent_id=b.id)
    assert "Ciclo" in exc.value.detail

    with pytest.raises(HTTPException) as exc:
        svc.validate_goal_parent(db_session, goal_id=None, parent_id=999999)
    assert "no existe" in exc.value.detail


# ─── parsers ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", GoalTemporality.ONEOFF),
        ("diario", GoalTemporality.DAILY),
        ("DAILY", GoalTemporality.DAILY),
        ("semanal", GoalTemporality.WEEKLY),
        ("weekly", GoalTemporality.WEEKLY),
        ("mensual", GoalTemporality.MONTHLY),
        ("monthly", GoalTemporality.MONTHLY),
        ("anual", GoalTemporality.ANNUAL),
        ("annual", GoalTemporality.ANNUAL),
        ("oneoff", GoalTemporality.ONEOFF),
        ("one-off", GoalTemporality.ONEOFF),
        ("única", GoalTemporality.ONEOFF),
        ("bogus", GoalTemporality.ONEOFF),
    ],
)
def test_parse_temporality_variants(text, expected):
    assert svc._parse_temporality(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", GoalFailConfig.STATIC),
        ("rollover", GoalFailConfig.ROLLOVER),
        ("traspaso", GoalFailConfig.ROLLOVER),
        ("snowball", GoalFailConfig.SNOWBALL),
        ("acumulativo", GoalFailConfig.SNOWBALL),
        ("static", GoalFailConfig.STATIC),
    ],
)
def test_parse_fail_config_variants(text, expected):
    assert svc._parse_fail_config(text) == expected


# ─── sync_goals_from_note ─────────────────────────────────────────────────────


def test_sync_goals_creates_and_updates(db_session):
    note = _note(db_session)
    content = "# Objetivo: 5 paginas @diario %snowball\n# Objetivo: leer libro\n"
    svc.sync_goals_from_note(db_session, note.id, content)
    db_session.flush()

    goals = db_session.query(Goal).filter(Goal.note_id == note.id).all()
    assert len(goals) == 2
    by_title = {g.title: g for g in goals}
    assert by_title["5 paginas"].temporality == GoalTemporality.DAILY
    assert by_title["5 paginas"].fail_config == GoalFailConfig.SNOWBALL
    assert by_title["5 paginas"].target_value == 5.0
    assert by_title["5 paginas"].measurement_type == GoalMeasurement.COUNT
    assert by_title["leer libro"].measurement_type == GoalMeasurement.BOOLEAN

    # Second sync: keep one goal (target updated while ACTIVE), drop the other
    # → the dropped goal is flagged pending_removal instead of deleted.
    svc.sync_goals_from_note(db_session, note.id, "# Objetivo: 5 paginas @semanal\n")
    db_session.flush()
    refreshed = {g.title: g for g in db_session.query(Goal).filter(Goal.note_id == note.id).all()}
    assert refreshed["5 paginas"].temporality == GoalTemporality.WEEKLY
    assert refreshed["leer libro"].pending_removal is True
    assert refreshed["leer libro"].state == GoalState.ACTIVE


def test_sync_goals_pending_removal_skips_terminal(db_session):
    note = _note(db_session)
    svc.sync_goals_from_note(db_session, note.id, "# Objetivo: viejo goal\n# Objetivo: keep me\n")
    db_session.flush()
    viejo = db_session.query(Goal).filter(Goal.title == "viejo goal").one()
    viejo.state = GoalState.COMPLETED
    viejo.is_completed = True
    db_session.flush()

    svc.sync_goals_from_note(db_session, note.id, "# Objetivo: keep me\n")
    db_session.flush()
    # Completed goals are not flagged for removal.
    assert viejo.pending_removal is False


# ─── resolve_pending_removal ──────────────────────────────────────────────────


def test_resolve_pending_removal_actions(db_session):
    delete_goal = _goal(db_session, title="del", pending_removal=True)
    manual_goal = _goal(db_session, title="man", pending_removal=True, note_id=None)
    note = _note(db_session)
    manual_goal.note_id = note.id
    cancel_goal = _goal(db_session, title="can", pending_removal=True)
    db_session.flush()

    assert svc.resolve_pending_removal(db_session, 999999, "delete") is None

    assert svc.resolve_pending_removal(db_session, delete_goal.id, "delete") is None
    assert db_session.get(Goal, delete_goal.id) is None

    kept = svc.resolve_pending_removal(db_session, manual_goal.id, "manual")
    assert kept is not None and kept.pending_removal is False and kept.note_id is None

    cancelled = svc.resolve_pending_removal(db_session, cancel_goal.id, "cancel")
    assert cancelled is not None and cancelled.state == GoalState.CANCELLED


# ─── progress helpers ─────────────────────────────────────────────────────────


def test_goal_progress_count_with_tag(db_session):
    tag = Tag(name="count-tag")
    db_session.add(tag)
    db_session.flush()
    # Pin one shared created_at — server_default func.now() is the transaction
    # time on PostgreSQL but per-statement wall clock on SQLite, so relying on
    # insertion order makes this test timing-flaky off-CI (#1595).
    ts = datetime.now(UTC)
    note = _note(db_session, created_at=ts)
    db_session.add(NoteTag(note_id=note.id, tag_id=tag.id))
    goal = _goal(
        db_session,
        tag_id=tag.id,
        measurement_type=GoalMeasurement.COUNT,
        target_value=10,
        current_value=3,
        created_at=ts,
    )
    db_session.flush()

    # COUNT + tag_id → progress is the number of tagged notes, not current_value.
    assert svc.get_goal_progress(goal, db_session) == 1.0

    # Non-count measurement falls back to current_value.
    goal.measurement_type = GoalMeasurement.BOOLEAN
    assert svc.get_goal_progress(goal, db_session) == 3.0


def test_bulk_goal_progress(db_session):
    tag = Tag(name="bulk-tag")
    db_session.add(tag)
    db_session.flush()
    # Same shared-timestamp pinning as test_goal_progress_count_with_tag (#1595).
    ts = datetime.now(UTC)
    note = _note(db_session, created_at=ts)
    db_session.add(NoteTag(note_id=note.id, tag_id=tag.id))
    count_goal = _goal(db_session, tag_id=tag.id, measurement_type=GoalMeasurement.COUNT, created_at=ts)
    plain = _goal(db_session, title="plain", current_value=7.0)
    db_session.flush()

    progress = svc.get_bulk_goal_progress([count_goal, plain], db_session)
    assert progress[count_goal.id] == 1.0
    assert progress[plain.id] == 7.0
    assert svc.get_bulk_goal_progress([], db_session) == {}


# ─── evaluate_active_goals ────────────────────────────────────────────────────


def test_evaluate_oneoff_completes_on_target(db_session):
    note = _note(db_session)
    goal = _goal(
        db_session,
        title="oneoff",
        temporality=GoalTemporality.ONEOFF,
        measurement_type=GoalMeasurement.COUNT,
        target_value=1.0,
        current_value=1.0,
        note_id=note.id,
    )
    db_session.commit()

    svc.evaluate_active_goals(db_session)
    db_session.refresh(goal)
    assert goal.state == GoalState.COMPLETED
    assert goal.is_completed is True
    assert goal.completed_at is not None


def test_evaluate_expired_static_fails(db_session):
    goal = _goal(
        db_session,
        title="expired",
        temporality=GoalTemporality.DAILY,
        fail_config=GoalFailConfig.STATIC,
        target_value=5.0,
        current_value=1.0,
        created_at=datetime.now(UTC) - timedelta(days=3),
    )
    db_session.commit()

    svc.evaluate_active_goals(db_session)
    db_session.refresh(goal)
    assert goal.state == GoalState.FAILED
    assert goal.current_value == 1.0


def test_evaluate_expired_rollover_carries_over(db_session):
    goal = _goal(
        db_session,
        title="rollover",
        temporality=GoalTemporality.WEEKLY,
        fail_config=GoalFailConfig.ROLLOVER,
        target_value=4.0,
        current_value=2.0,
        created_at=datetime.now(UTC) - timedelta(days=10),
    )
    db_session.commit()

    svc.evaluate_active_goals(db_session)
    db_session.refresh(goal)
    # Rollover: same row re-activated for the new period, progress reset.
    # created_at is stored naive-UTC, so compare against a naive bound.
    assert goal.state == GoalState.ACTIVE
    assert goal.current_value == 0.0
    assert goal.created_at > datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=5)


def test_evaluate_expired_snowball_spawns_accumulated(db_session):
    goal = _goal(
        db_session,
        title="snowball",
        temporality=GoalTemporality.DAILY,
        fail_config=GoalFailConfig.SNOWBALL,
        target_value=10.0,
        current_value=4.0,
        created_at=datetime.now(UTC) - timedelta(days=2),
    )
    db_session.commit()

    svc.evaluate_active_goals(db_session)
    db_session.refresh(goal)
    assert goal.state == GoalState.FAILED
    assert goal.current_value == 4.0

    child = db_session.query(Goal).filter(Goal.title == "snowball", Goal.state == GoalState.ACTIVE).one()
    # shortfall = 10 - 4 = 6 → new target = 10 + 6 = 16
    assert child.target_value == 16.0
    assert child.parent_id == goal.id


def test_evaluate_expired_but_target_reached_completes(db_session):
    """An expired goal that actually hit its target completes instead of failing."""
    goal = _goal(
        db_session,
        title="late-finisher",
        temporality=GoalTemporality.DAILY,
        target_value=2.0,
        current_value=2.0,
        created_at=datetime.now(UTC) - timedelta(days=2),
    )
    db_session.commit()

    svc.evaluate_active_goals(db_session)
    db_session.refresh(goal)
    assert goal.state == GoalState.COMPLETED
    assert goal.is_completed is True


# ─── get_goal_streak ──────────────────────────────────────────────────────────


def test_goal_streak_empty_and_consecutive(db_session):
    assert svc.get_goal_streak(db_session) == {"current_streak": 0, "best_streak": 0}

    today = get_local_today()
    for offset in (0, 1, 2):
        _goal(
            db_session,
            title=f"done-{offset}",
            temporality=GoalTemporality.DAILY,
            state=GoalState.COMPLETED,
            is_completed=True,
            completed_at=datetime.combine(today - timedelta(days=offset), datetime.min.time()).replace(tzinfo=UTC),
        )
    # A non-daily completion must not count.
    _goal(
        db_session,
        title="weekly-done",
        temporality=GoalTemporality.WEEKLY,
        state=GoalState.COMPLETED,
        is_completed=True,
        completed_at=datetime.now(UTC),
    )
    db_session.commit()

    streak = svc.get_goal_streak(db_session)
    assert streak["current_streak"] == 3
    assert streak["best_streak"] == 3


def test_goal_streak_gaps_reset_best(db_session):
    today = get_local_today()
    # Best run: 4 consecutive days ending 5 days ago; current run: today only.
    for offset in range(5, 9):
        _goal(
            db_session,
            title=f"old-{offset}",
            temporality=GoalTemporality.DAILY,
            state=GoalState.COMPLETED,
            is_completed=True,
            completed_at=datetime.combine(today - timedelta(days=offset), datetime.min.time()).replace(tzinfo=UTC),
        )
    _goal(
        db_session,
        title="today-done",
        temporality=GoalTemporality.DAILY,
        state=GoalState.COMPLETED,
        is_completed=True,
        completed_at=datetime.now(UTC),
    )
    db_session.commit()

    streak = svc.get_goal_streak(db_session)
    assert streak["current_streak"] == 1
    assert streak["best_streak"] == 4
