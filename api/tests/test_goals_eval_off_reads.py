"""#1519 — goal read endpoints must not run the evaluator.

``GET /goals`` and ``GET /goals/execution-queue`` used to call
``evaluate_active_goals(db)`` inline, so every read paid for the full pass
— active-goal scan, bulk progress join, per-expired-goal vault file writes
and a commit. Evaluation now runs on the periodic background pass
(``run_goal_evaluation_pass``); these tests pin both halves: reads are
side-effect free, and the scheduled pass still applies transitions.
"""

import contextlib
from datetime import UTC, datetime, timedelta

from models.goal import Goal, GoalFailConfig, GoalState, GoalTemporality
from services import goal_service as svc


def _goal(db, **kwargs) -> Goal:
    goal = Goal(title=kwargs.pop("title", "goal"), **kwargs)
    db.add(goal)
    db.flush()
    return goal


def _expired_goal(db) -> Goal:
    """A DAILY STATIC goal created 3 days ago — always past expiry."""
    return _goal(
        db,
        title="expired",
        temporality=GoalTemporality.DAILY,
        fail_config=GoalFailConfig.STATIC,
        target_value=5.0,
        current_value=0.0,
        created_at=datetime.now(UTC) - timedelta(days=3),
    )


def _eval_guards(monkeypatch) -> list[str]:
    """Arm spies on every path a read could reach the evaluator through.

    - ``services.goal_service.evaluate_active_goals`` catches module-level
      callers (and the service calling itself via the module namespace).
    - ``routers.goals.evaluate_active_goals`` (raising=False) catches a
      regression that re-adds ``from services.goal_service import
      evaluate_active_goals`` to the router — the name is bound at import
      time, so the service-level spy alone would miss it.
    - ``services.joidy_vault_writer._write_goal_file`` guards the heaviest
      side effect directly (vault file writes).
    """
    calls: list[str] = []

    def _eval_spy(*args, **kwargs):
        calls.append("evaluate")

    def _write_spy(*args, **kwargs):
        calls.append("vault-write")

    monkeypatch.setattr("services.goal_service.evaluate_active_goals", _eval_spy)
    monkeypatch.setattr("routers.goals.evaluate_active_goals", _eval_spy, raising=False)
    monkeypatch.setattr("services.joidy_vault_writer._write_goal_file", _write_spy)
    monkeypatch.setattr("routers.goals._write_goal_file", _write_spy)
    return calls


def test_list_goals_does_not_evaluate(client, db_session, tmp_path, monkeypatch):
    expired = _expired_goal(db_session)
    db_session.commit()
    calls = _eval_guards(monkeypatch)

    resp = client.get("/goals/")
    assert resp.status_code == 200, resp.text

    assert calls == []
    # The read served persisted state: the expired goal was NOT failed.
    db_session.expire_all()
    assert db_session.get(Goal, expired.id).state == GoalState.ACTIVE
    # And no goal file appeared in the vault (isolated tmp vault fixture).
    assert not list((tmp_path / "isolated-vault" / "Objetivos").glob("*.md"))


def test_execution_queue_does_not_evaluate(client, db_session, tmp_path, monkeypatch):
    expired = _expired_goal(db_session)
    db_session.commit()
    calls = _eval_guards(monkeypatch)

    resp = client.get("/goals/execution-queue")
    assert resp.status_code == 200, resp.text

    assert calls == []
    db_session.expire_all()
    assert db_session.get(Goal, expired.id).state == GoalState.ACTIVE
    assert not list((tmp_path / "isolated-vault" / "Objetivos").glob("*.md"))


def test_scheduled_pass_processes_expired_goal(db_session, monkeypatch):
    """The background pass entry point drives the same evaluator.

    ``database.SessionLocal`` is monkeypatched to hand back the test
    session (wrapped in ``nullcontext`` so the ``with`` block does not
    close it) so ``run_goal_evaluation_pass`` operates inside the per-test
    savepoint transaction.
    """
    expired = _expired_goal(db_session)
    db_session.commit()
    monkeypatch.setattr("database.SessionLocal", lambda: contextlib.nullcontext(db_session))
    # Skip real vault I/O — covered by the evaluator's own tests.
    monkeypatch.setattr("services.joidy_vault_writer.get_objectives_dir", lambda: None)

    svc.run_goal_evaluation_pass()

    db_session.expire_all()
    assert db_session.get(Goal, expired.id).state == GoalState.FAILED


def test_scheduled_pass_surfaces_errors_for_retry(db_session, monkeypatch):
    """A failing pass propagates — the loop logs it and retries next tick."""
    monkeypatch.setattr("database.SessionLocal", lambda: contextlib.nullcontext(db_session))
    monkeypatch.setattr(
        "services.goal_service.evaluate_active_goals",
        lambda db: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    try:
        svc.run_goal_evaluation_pass()
    except RuntimeError as e:
        assert str(e) == "boom"
    else:
        raise AssertionError("expected the evaluation error to propagate")
