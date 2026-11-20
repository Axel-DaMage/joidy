"""Telegram bot quick-capture service (#1132).

Translates Telegram bot commands received on ``POST /telegram/webhook``
into Joidy operations:

- ``/note <text>``    → creates a note persisted to the Obsidian vault
- ``/goal <text>``    → creates a goal
- ``/checkin <1-5> [note]`` → records today's mood entry
- ``/ask <question>`` → answers via the ai-service ``/rag`` endpoint
- ``/status``         → XP, streaks and today's goals
- ``/start``, ``/help`` → usage help

Every incoming update is persisted to the ``telegram_events`` table for
auditing and webhook retry de-duplication. Replies are sent back through
the Telegram ``sendMessage`` API when ``TELEGRAM_BOT_TOKEN`` is set.

Configuration (all via Pydantic ``Settings`` / ``.env``):
- ``TELEGRAM_BOT_TOKEN`` — required; without it the webhook answers 503.
- ``TELEGRAM_ALLOWED_USER_ID`` — optional; restricts the bot to one user.
- ``TELEGRAM_WEBHOOK_SECRET`` — optional; verified against Telegram's
  ``X-Telegram-Bot-Api-Secret-Token`` header when set.
"""

import hmac
import logging
import os
import re
from typing import Any

import httpx
from config import settings
from middleware.correlation_id import get_correlation_id
from models.gamification import UserStats
from models.goal import Goal, GoalMeasurement, GoalState, GoalTemporality
from models.telegram_event import TelegramEvent
from services.gamification_engine import get_plant_stages
from services.goal_service import get_bulk_goal_progress
from services.http_client import http_client
from services.mood_service import create_or_update_mood, get_today_mood
from services.sanitizer import sanitize_title
from services.timezone_utils import get_local_now
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"

# Single-user deployment: gamification stats and mood entries live under
# the synthetic user id 1 everywhere else in the codebase.
TELEGRAM_USER_ID = 1

# Telegram sendMessage hard limit is 4096 chars; stay below it.
MAX_REPLY_CHARS = 4000
MAX_STORED_TEXT_CHARS = 4000

HELP_TEXT = (
    "Joidy quick capture bot. Commands:\n"
    "/note <text> — save a note to your vault\n"
    "/goal <text> — create a goal\n"
    "/checkin <1-5> [note] — record today's mood\n"
    "/ask <question> — ask your notes (RAG)\n"
    "/status — XP, streaks and today's goals\n"
    "/help — this message"
)


def is_configured() -> bool:
    """True when a bot token is configured."""
    return bool(settings.telegram_bot_token)


def _allowed_user_id() -> int | None:
    """Configured ``TELEGRAM_ALLOWED_USER_ID`` as int, or None when unset/invalid."""
    raw = (settings.telegram_allowed_user_id or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        logger.warning("TELEGRAM_ALLOWED_USER_ID is not a valid integer: %r", raw)
        return None


def is_user_restricted() -> bool:
    """True when ``TELEGRAM_ALLOWED_USER_ID`` restricts the bot to one user."""
    return _allowed_user_id() is not None


def is_authorized(telegram_user_id: int | None) -> bool:
    """True when the sender may use the bot.

    Without ``TELEGRAM_ALLOWED_USER_ID`` the bot answers anyone — useful for
    first-time setup (send any message, read your id from the logs/events).
    """
    allowed = _allowed_user_id()
    if allowed is None:
        return True
    return telegram_user_id == allowed


def verify_webhook_secret(header_value: str | None) -> bool:
    """Verify Telegram's ``X-Telegram-Bot-Api-Secret-Token`` header.

    Only enforced when ``TELEGRAM_WEBHOOK_SECRET`` is configured — the same
    value must be passed as ``secret_token`` to Telegram's ``setWebhook``.
    """
    expected = settings.telegram_webhook_secret
    if not expected:
        return True
    return hmac.compare_digest(header_value or "", expected)


def parse_command(text: str) -> tuple[str, str] | None:
    """Parse a bot command, tolerating the ``/cmd@BotName`` suffix.

    ``"/note@JoidyBot buy milk"`` → ``("note", "buy milk")``.
    Returns ``None`` for non-command messages.
    """
    text = (text or "").strip()
    if not text.startswith("/"):
        return None
    head, _, args = text.partition(" ")
    command = head[1:].split("@", 1)[0].strip().lower()
    if not command:
        return None
    return command, args.strip()


def log_event(
    db: Session,
    *,
    update_id: int | None = None,
    telegram_user_id: int | None = None,
    chat_id: int | None = None,
    command: str = "",
    message_text: str = "",
    status: str = "received",
    response: str = "",
    error: str | None = None,
) -> TelegramEvent:
    """Persist an interaction row in ``telegram_events``."""
    event = TelegramEvent(
        update_id=update_id,
        telegram_user_id=telegram_user_id,
        chat_id=chat_id,
        command=command[:32],
        message_text=(message_text or "")[:MAX_STORED_TEXT_CHARS],
        status=status,
        response=(response or "")[:MAX_STORED_TEXT_CHARS],
        error=error,
    )
    db.add(event)
    db.commit()
    return event


async def send_message(chat_id: int, text: str) -> bool:
    """Send a reply through the Telegram Bot API. Best-effort."""
    if not is_configured() or not chat_id or not text:
        return False
    url = f"{TELEGRAM_API}/bot{settings.telegram_bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text[:MAX_REPLY_CHARS]}
    try:
        async with http_client(timeout=15.0) as client:
            r = await client.post(url, json=payload)
            r.raise_for_status()
            return True
    except httpx.HTTPError as exc:
        logger.warning("Telegram sendMessage failed: %s", exc)
        return False


async def set_webhook(url: str) -> dict[str, Any]:
    """Register the webhook URL with Telegram's ``setWebhook`` API."""
    if not is_configured():
        raise RuntimeError("Telegram bot is not configured (TELEGRAM_BOT_TOKEN)")
    payload: dict[str, Any] = {"url": url, "allowed_updates": ["message"]}
    if settings.telegram_webhook_secret:
        payload["secret_token"] = settings.telegram_webhook_secret
    async with http_client(timeout=15.0) as client:
        r = await client.post(
            f"{TELEGRAM_API}/bot{settings.telegram_bot_token}/setWebhook",
            json=payload,
        )
        r.raise_for_status()
        return r.json()


async def delete_webhook() -> dict[str, Any]:
    """Remove the webhook (fall back to manual polling/getMe debugging)."""
    if not is_configured():
        raise RuntimeError("Telegram bot is not configured (TELEGRAM_BOT_TOKEN)")
    async with http_client(timeout=15.0) as client:
        r = await client.post(f"{TELEGRAM_API}/bot{settings.telegram_bot_token}/deleteWebhook")
        r.raise_for_status()
        return r.json()


# ── Command handlers ──────────────────────────────


def _usage(usage: str) -> str:
    return f"Usage: {usage}\n\n{HELP_TEXT}"


def _note_source_path(title: str) -> str | None:
    """Build a unique vault path for a quick-capture note.

    Returns ``None`` when no vault is configured — the note is still created
    in the database, just without a backing ``.md`` file.
    """
    vault = (settings.obsidian_vault_path or "").rstrip("/")
    if not vault:
        return None
    now = get_local_now()
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", title)[:40].strip("-").lower() or "note"
    folder = os.path.join(vault, "Telegram")
    try:
        os.makedirs(folder, exist_ok=True)
    except OSError as exc:
        logger.warning("Could not create Telegram vault folder %s: %s", folder, exc)
    return f"{folder}/{now:%Y%m%d}-{now:%H%M%S}-{slug}.md"


def _cmd_note(db: Session, args: str) -> str:
    if not args:
        return _usage("/note <text>")
    from services.note_service import create_note  # local import: avoid cycles

    title = args.splitlines()[0].strip()[:80] or "Telegram note"
    note, gami = create_note(
        db,
        title=title,
        content=args,
        tags=["telegram"],
        source="telegram",
        source_path=_note_source_path(title),
    )
    reply = f"Note saved: {note.title}"
    if gami and gami.xp_awarded:
        reply += f" (+{gami.xp_awarded} XP)"
    return reply


def _cmd_goal(db: Session, args: str) -> str:
    if not args:
        return _usage("/goal <text>")
    goal = Goal(
        title=sanitize_title(args[:500]),
        temporality=GoalTemporality.ONEOFF,
        measurement_type=GoalMeasurement.BOOLEAN,
        target_value=1.0,
        state=GoalState.ACTIVE,
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return f"Goal created: {goal.title}"


def _cmd_checkin(db: Session, args: str) -> str:
    if not args:
        return _usage("/checkin <1-5> [note]")
    parts = args.split(None, 1)
    try:
        score = int(parts[0])
    except ValueError:
        return _usage("/checkin <1-5> [note]")
    if score < 1 or score > 5:
        return "Mood score must be between 1 and 5."
    note = parts[1] if len(parts) > 1 else None
    create_or_update_mood(db, TELEGRAM_USER_ID, score, note)
    return f"Check-in saved: mood {score}/5 for today."


async def _cmd_ask(db: Session, args: str) -> str:
    if not args:
        return _usage("/ask <question>")
    if not settings.ai_service_enabled:
        return "AI features are disabled (AI_SERVICE_ENABLED=false)."
    headers = {"X-Request-ID": get_correlation_id()}
    if settings.internal_secret:
        headers["X-Internal-Secret"] = settings.internal_secret
    try:
        async with http_client(timeout=60.0) as client:
            r = await client.post(
                f"{settings.ai_service_url}/rag",
                json={"question": args[:1000], "top_k": 5},
                headers=headers,
            )
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPError as exc:
        logger.warning("ai-service /rag call failed: %s", exc)
        return "The AI service is unavailable right now. Try again later."

    status = data.get("status")
    if status == "success" and data.get("answer"):
        return str(data["answer"])
    if status == "disabled":
        return "No AI provider is configured."
    if status == "circuit_open":
        return "The AI provider is temporarily unavailable. Try again later."
    return "I could not generate an answer for that question."


def _cmd_status(db: Session) -> str:
    stats = db.query(UserStats).filter(UserStats.id == 1).first()
    xp = stats.total_xp if stats else 0
    current_streak = stats.current_streak if stats else 0
    longest_streak = stats.longest_streak if stats else 0

    stages = get_plant_stages(db)
    stage_idx = stats.plant_stage if stats else 0
    stage_idx = max(0, min(stage_idx, len(stages) - 1))
    plant_name = stages[stage_idx][1] if stages else "semilla"

    lines = [
        "Status",
        f"XP: {xp} (plant: {plant_name})",
        f"Streak: {current_streak} day(s) — best: {longest_streak}",
    ]

    mood = get_today_mood(db, TELEGRAM_USER_ID)
    lines.append(f"Mood today: {mood.score}/5" if mood else "Mood today: not recorded — /checkin <1-5>")

    daily_goals = (
        db.query(Goal)
        .filter(Goal.temporality == GoalTemporality.DAILY, Goal.state == GoalState.ACTIVE)
        .order_by(Goal.created_at.asc())
        .limit(20)
        .all()
    )
    if daily_goals:
        progress = get_bulk_goal_progress(daily_goals, db)
        lines.append("Today's goals:")
        for goal in daily_goals:
            done = goal.is_completed or progress.get(goal.id, 0.0) >= goal.target_value
            mark = "[x]" if done else "[ ]"
            lines.append(f"  {mark} {goal.title} ({goal.current_value:g}/{goal.target_value:g})")
    else:
        lines.append("No active daily goals.")
    return "\n".join(lines)


async def _dispatch(db: Session, command: str, args: str) -> str:
    if command in ("start", "help"):
        return HELP_TEXT
    if command == "note":
        return _cmd_note(db, args)
    if command == "goal":
        return _cmd_goal(db, args)
    if command == "checkin":
        return _cmd_checkin(db, args)
    if command == "ask":
        return await _cmd_ask(db, args)
    if command == "status":
        return _cmd_status(db)
    return f"Unknown command /{command}. Try /help."


def _already_processed(db: Session, update_id: int | None) -> bool:
    """True when this ``update_id`` was already handled.

    Telegram retries webhook deliveries until it gets a 200, so network
    flakes can deliver the same update twice — dedup keeps ``/note`` from
    creating duplicate notes.
    """
    if update_id is None:
        return False
    return (
        db.query(TelegramEvent)
        .filter(TelegramEvent.update_id == update_id, TelegramEvent.status == "processed")
        .first()
        is not None
    )


async def handle_update(db: Session, update: dict[str, Any]) -> dict[str, Any]:
    """Process one Telegram webhook update and persist a ``telegram_events`` row.

    Always returns a JSON-serializable dict; the router answers 200 so
    Telegram does not retry. ``handled`` is False for unsupported updates,
    duplicates and unauthorized senders.
    """
    update_id = update.get("update_id")
    raw_message = update.get("message")
    message = raw_message if isinstance(raw_message, dict) else {}
    text = message.get("text") or ""
    from_user = message.get("from")
    telegram_user_id = from_user.get("id") if isinstance(from_user, dict) else None
    chat = message.get("chat")
    chat_id = chat.get("id") if isinstance(chat, dict) else None

    base: dict[str, Any] = {
        "update_id": update_id if isinstance(update_id, int) else None,
        "telegram_user_id": telegram_user_id if isinstance(telegram_user_id, int) else None,
        "chat_id": chat_id if isinstance(chat_id, int) else None,
        "message_text": text,
    }

    if not isinstance(text, str) or not text:
        log_event(db, **base, status="ignored", response="unsupported update type")
        return {"handled": False, "reason": "unsupported_update"}

    if _already_processed(db, base["update_id"]):
        log_event(db, **base, status="ignored", response="duplicate update")
        return {"handled": False, "reason": "duplicate"}

    if not is_authorized(base["telegram_user_id"]):
        log_event(db, **base, status="unauthorized", response="sender not in TELEGRAM_ALLOWED_USER_ID")
        logger.info("Ignoring Telegram update from unauthorized user %s", base["telegram_user_id"])
        return {"handled": False, "reason": "unauthorized"}

    parsed = parse_command(text)
    if parsed is None:
        reply = "I only understand commands. Try /help."
        log_event(db, **base, command="message", status="processed", response=reply)
    else:
        command, args = parsed
        try:
            reply = await _dispatch(db, command, args)
            log_event(db, **base, command=command, status="processed", response=reply)
        except Exception as exc:
            logger.exception("Telegram command /%s failed", command)
            reply = "Something went wrong processing that command."
            log_event(db, **base, command=command, status="error", response=reply, error=str(exc)[:1000])

    if base["chat_id"]:
        await send_message(base["chat_id"], reply)

    return {
        "handled": True,
        "command": parsed[0] if parsed else "message",
        "reply": reply,
    }
