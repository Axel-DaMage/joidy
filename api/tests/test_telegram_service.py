"""Tests for the Telegram bot quick-capture service (#1132).

Covers command parsing, the /note → vault note, /goal, /checkin, /ask
(mocked ai-service), /status flows, telegram_events persistence, sender
authorization, webhook secret verification and update_id de-duplication.

Note on isolation: assertions filter by unique per-test ``update_id``s and
marker strings instead of global ``count() == 0`` checks. The local SQLite
fallback commits through the savepoint-scoped fixture (PostgreSQL in CI
rolls back correctly), so tests must tolerate rows left by earlier tests.
"""

import asyncio
from contextlib import asynccontextmanager
from itertools import count
from pathlib import Path
from unittest import mock

from config import settings
from models.gamification import UserStats
from models.goal import Goal, GoalState, GoalTemporality
from models.mood_entry import MoodEntry
from models.note import Note
from models.telegram_event import TelegramEvent
from services import telegram_service as ts
from sqlalchemy.orm import Session

_update_ids = count(1000)


def _update(text: str, update_id: int | None = None, user_id: int = 42, chat_id: int = 99) -> dict:
    """Build a minimal Telegram webhook update payload."""
    return {
        "update_id": update_id if update_id is not None else next(_update_ids),
        "message": {
            "message_id": 1,
            "from": {"id": user_id, "first_name": "Test"},
            "chat": {"id": chat_id, "type": "private"},
            "text": text,
        },
    }


def _handle(db_session: Session, update: dict) -> dict:
    return asyncio.run(ts.handle_update(db_session, update))


def _event(db_session: Session, update_id: int) -> TelegramEvent:
    event = (
        db_session.query(TelegramEvent)
        .filter(TelegramEvent.update_id == update_id)
        .order_by(TelegramEvent.id.desc())
        .first()
    )
    assert event is not None
    return event


def _notes_titled(db_session: Session, title: str) -> list[Note]:
    return db_session.query(Note).filter(Note.title == title).all()


# ── Pure helpers ──────────────────────────────────


class TestParseCommand:
    def test_simple_command(self):
        assert ts.parse_command("/note buy milk") == ("note", "buy milk")

    def test_command_with_bot_suffix(self):
        assert ts.parse_command("/note@JoidyBot buy milk") == ("note", "buy milk")

    def test_command_without_args(self):
        assert ts.parse_command("/status") == ("status", "")

    def test_non_command_returns_none(self):
        assert ts.parse_command("just some text") is None
        assert ts.parse_command("") is None
        assert ts.parse_command("/") is None

    def test_command_is_lowercased(self):
        assert ts.parse_command("/NOTE text") == ("note", "text")


class TestAuthAndSecret:
    def test_authorized_when_no_allowlist(self):
        with mock.patch.object(settings, "telegram_allowed_user_id", ""):
            assert ts.is_authorized(123) is True
            assert ts.is_user_restricted() is False

    def test_authorized_only_allowed_user(self):
        with mock.patch.object(settings, "telegram_allowed_user_id", "42"):
            assert ts.is_authorized(42) is True
            assert ts.is_authorized(43) is False
            assert ts.is_authorized(None) is False
            assert ts.is_user_restricted() is True

    def test_invalid_allowlist_value_fails_open(self):
        with mock.patch.object(settings, "telegram_allowed_user_id", "abc"):
            assert ts.is_authorized(42) is True

    def test_secret_not_required_when_unset(self):
        with mock.patch.object(settings, "telegram_webhook_secret", ""):
            assert ts.verify_webhook_secret(None) is True
            assert ts.verify_webhook_secret("anything") is True

    def test_secret_must_match(self):
        with mock.patch.object(settings, "telegram_webhook_secret", "s3cret"):
            assert ts.verify_webhook_secret("s3cret") is True
            assert ts.verify_webhook_secret("wrong") is False
            assert ts.verify_webhook_secret(None) is False


# ── Command handling ──────────────────────────────


class TestNoteCommand:
    def test_note_creates_note_and_logs_event(self, db_session: Session, tmp_path: Path):
        update = _update("/note remember the milk telegramtest")
        with mock.patch.object(settings, "obsidian_vault_path", str(tmp_path)):
            result = _handle(db_session, update)

        assert result["handled"] is True
        assert result["command"] == "note"
        assert "Note saved" in result["reply"]

        note = (
            db_session.query(Note)
            .filter(
                Note.title == "remember the milk telegramtest",
                Note.source == "telegram",
            )
            .one()
        )
        assert note.content == "remember the milk telegramtest"
        assert note.source_path and note.source_path.startswith(str(tmp_path))
        # AC1: the note is written into the vault.
        written = Path(note.source_path)
        assert written.is_file()
        assert written.read_text() == "remember the milk telegramtest"

        event = _event(db_session, update["update_id"])
        assert event is not None
        assert event.command == "note"
        assert event.status == "processed"

    def test_note_without_args_returns_usage(self, db_session: Session):
        update = _update("/note")
        result = _handle(db_session, update)
        assert result["handled"] is True, result
        assert "Usage" in result["reply"]
        event = _event(db_session, update["update_id"])
        assert event.status == "processed"


class TestGoalCommand:
    def test_goal_creates_goal(self, db_session: Session):
        update = _update("/goal run 5k telegramtest")
        result = _handle(db_session, update)
        assert "Goal created" in result["reply"]

        goal = db_session.query(Goal).filter(Goal.title == "run 5k telegramtest").one()
        assert goal.state == GoalState.ACTIVE
        assert goal.temporality == GoalTemporality.ONEOFF
        assert _event(db_session, update["update_id"]).command == "goal"

    def test_goal_without_args_returns_usage(self, db_session: Session):
        update = _update("/goal")
        result = _handle(db_session, update)
        assert "Usage" in result["reply"]
        event = _event(db_session, update["update_id"])
        assert event.command == "goal"
        assert event.status == "processed"


class TestCheckinCommand:
    def test_checkin_records_mood(self, db_session: Session):
        update = _update("/checkin 4 feeling telegramtest")
        result = _handle(db_session, update)
        assert "4/5" in result["reply"]

        mood = db_session.query(MoodEntry).filter(MoodEntry.note == "feeling telegramtest").one()
        assert mood.score == 4
        assert mood.user_id == ts.TELEGRAM_USER_ID

    def test_checkin_rejects_out_of_range(self, db_session: Session):
        before = db_session.query(MoodEntry).count()
        result = _handle(db_session, _update("/checkin 9"))
        assert "between 1 and 5" in result["reply"]
        assert db_session.query(MoodEntry).count() == before

    def test_checkin_rejects_non_numeric(self, db_session: Session):
        before = db_session.query(MoodEntry).count()
        result = _handle(db_session, _update("/checkin great"))
        assert "Usage" in result["reply"]
        assert db_session.query(MoodEntry).count() == before


class TestStatusCommand:
    def test_status_reports_xp_streak_and_goals(self, db_session: Session):
        # Upsert the single-user stats row — earlier tests may have created
        # it via gamification events (SQLite fallback leaks commits).
        stats = db_session.query(UserStats).filter(UserStats.id == 1).first()
        if stats is None:
            stats = UserStats(id=1)
            db_session.add(stats)
        stats.total_xp = 1500
        stats.current_streak = 3
        stats.longest_streak = 10
        stats.plant_stage = 2
        db_session.add(
            Goal(
                title="drink water telegramtest",
                temporality=GoalTemporality.DAILY,
                state=GoalState.ACTIVE,
                target_value=8,
                current_value=3,
            )
        )
        db_session.commit()

        result = _handle(db_session, _update("/status"))
        reply = result["reply"]
        assert "1500" in reply
        assert "3 day(s)" in reply
        assert "10" in reply
        assert "drink water telegramtest" in reply
        assert "3/8" in reply

    def test_status_always_reports_core_fields(self, db_session: Session):
        result = _handle(db_session, _update("/status"))
        reply = result["reply"]
        assert "XP:" in reply
        assert "Streak:" in reply
        assert "Mood today:" in reply
        assert _event(db_session, 0) is None  # sanity: helper filters by id


class _FakeAIResponse:
    def __init__(self, data: dict):
        self._data = data

    def raise_for_status(self):
        return None

    def json(self):
        return self._data


class _FakeAIClient:
    def __init__(self, data: dict):
        self._data = data
        self.requests: list[dict] = []

    async def post(self, url, json=None, headers=None):
        self.requests.append({"url": url, "json": json})
        return _FakeAIResponse(self._data)


def _patch_ai(payload: dict):
    """Patch the pooled http_client used for ai-service calls."""
    client = _FakeAIClient(payload)

    @asynccontextmanager
    async def _cm(timeout: float = 30.0):
        yield client

    return mock.patch.object(ts, "http_client", _cm), client


class TestAskCommand:
    def test_ask_returns_rag_answer(self, db_session: Session):
        patcher, client = _patch_ai({"status": "success", "answer": "The answer is 42."})
        update = _update("/ask what is the meaning?")
        with patcher:
            result = _handle(db_session, update)

        assert result["reply"] == "The answer is 42."
        assert client.requests[0]["json"]["question"] == "what is the meaning?"
        assert _event(db_session, update["update_id"]).command == "ask"

    def test_ask_without_args_returns_usage(self, db_session: Session):
        result = _handle(db_session, _update("/ask"))
        assert "Usage" in result["reply"]

    def test_ask_reports_unavailable_ai(self, db_session: Session):
        patcher, _client = _patch_ai({"status": "disabled", "answer": ""})
        with patcher:
            result = _handle(db_session, _update("/ask anything"))
        assert "No AI provider" in result["reply"]


# ── Update handling edge cases ────────────────────


class TestUpdateHandling:
    def test_plain_message_gets_help_hint(self, db_session: Session):
        update = _update("hello bot")
        result = _handle(db_session, update)
        assert result["handled"] is True
        assert result["command"] == "message"
        assert "/help" in result["reply"]
        assert _event(db_session, update["update_id"]).status == "processed"

    def test_unknown_command(self, db_session: Session):
        update = _update("/fly to the moon")
        result = _handle(db_session, update)
        assert "Unknown command" in result["reply"]
        assert _event(db_session, update["update_id"]).command == "fly"

    def test_unauthorized_user_is_ignored(self, db_session: Session):
        update = _update("/note secret telegramtest", user_id=8)
        with mock.patch.object(settings, "telegram_allowed_user_id", "7"):
            result = _handle(db_session, update)

        assert result["handled"] is False
        assert result["reason"] == "unauthorized"
        assert _notes_titled(db_session, "secret telegramtest") == []
        assert _event(db_session, update["update_id"]).status == "unauthorized"

    def test_duplicate_update_is_deduplicated(self, db_session: Session):
        update = _update("/note only once telegramtest")
        first = _handle(db_session, update)
        second = _handle(db_session, update)

        assert first["handled"] is True
        assert second["handled"] is False
        assert second["reason"] == "duplicate"
        assert len(_notes_titled(db_session, "only once telegramtest")) == 1

        statuses = [
            e.status
            for e in db_session.query(TelegramEvent).filter(TelegramEvent.update_id == update["update_id"]).all()
        ]
        assert statuses.count("processed") == 1
        assert statuses.count("ignored") == 1

    def test_non_message_update_is_ignored(self, db_session: Session):
        update_id = next(_update_ids)
        result = _handle(db_session, {"update_id": update_id, "callback_query": {"id": "x"}})
        assert result["handled"] is False
        assert result["reason"] == "unsupported_update"
        assert _event(db_session, update_id).status == "ignored"


# ── Webhook router ────────────────────────────────


class TestWebhookRouter:
    def test_webhook_503_when_not_configured(self, client):
        with mock.patch.object(settings, "telegram_bot_token", ""):
            resp = client.post("/telegram/webhook", json=_update("/status"))
        assert resp.status_code == 503

    def test_webhook_rejects_bad_secret(self, client):
        with (
            mock.patch.object(settings, "telegram_bot_token", "fake-token"),
            mock.patch.object(settings, "telegram_webhook_secret", "s3cret"),
        ):
            resp = client.post("/telegram/webhook", json=_update("/status"))
        assert resp.status_code == 401

    def test_webhook_processes_update(self, client):
        with (
            mock.patch.object(settings, "telegram_bot_token", "fake-token"),
            mock.patch.object(settings, "telegram_allowed_user_id", ""),
            mock.patch.object(settings, "telegram_webhook_secret", "s3cret"),
            mock.patch.object(ts, "send_message", new=mock.AsyncMock(return_value=True)),
        ):
            resp = client.post(
                "/telegram/webhook",
                json=_update("/status"),
                headers={"X-Telegram-Bot-Api-Secret-Token": "s3cret"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["handled"] is True
        assert body["command"] == "status"

    def test_telegram_status_requires_auth(self, client_no_auth):
        resp = client_no_auth.get("/telegram/status")
        assert resp.status_code == 401

    def test_telegram_status(self, client):
        with (
            mock.patch.object(settings, "telegram_bot_token", ""),
            mock.patch.object(settings, "telegram_allowed_user_id", ""),
            mock.patch.object(settings, "telegram_webhook_secret", ""),
        ):
            resp = client.get("/telegram/status")
        assert resp.status_code == 200
        assert resp.json() == {
            "configured": False,
            "allowed_user_restricted": False,
            "webhook_secret_set": False,
        }
