"""AI planning suggestions (#1237): prompt building + defensive response parsing.

The LLM is asked to slot open tasks into a planning window without overlapping
the user's busy blocks (Google Calendar events). Model output is untrusted:
this module strips markdown fences, tolerates messy JSON, and validates every
suggestion against the input task ids, the week range and the busy blocks —
invalid entries are dropped, never passed through.
"""

import json
import logging
import re
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from clients.prompts import PLAN_SUGGEST_PROMPT

logger = logging.getLogger(__name__)

# Used when a task arrives without an explicit duration.
DEFAULT_DURATION_MINUTES = 30

# Prompt-level hint for sane placement; the hard constraint is busy-block
# non-overlap, so this stays advisory rather than enforced in the validator.
WORKING_HOURS_HINT = "08:00-21:00"

_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$")


def _local_zone(tz_name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def build_plan_prompt(
    tasks: list[dict],
    busy_blocks: list[dict],
    week_start: str,
    week_end: str,
    timezone: str,
    context_hint: str | None = None,
) -> str:
    """Render the scheduling prompt sent to the LLM provider."""
    if tasks:
        task_lines = "\n".join(
            f"- id={t['id']} | priority={t.get('priority', 'MEDIUM')} | "
            f"duration={t.get('duration_minutes') or DEFAULT_DURATION_MINUTES}min | {t.get('title', '')}"
            for t in tasks
        )
    else:
        task_lines = "(none)"

    if busy_blocks:
        busy_lines = "\n".join(f"- {b.get('start')} -> {b.get('end') or '(no end)'}" for b in busy_blocks)
    else:
        busy_lines = "(none — every slot in the window is free)"

    hint = context_hint.strip() if context_hint else ""
    return PLAN_SUGGEST_PROMPT.format(
        timezone=timezone or "UTC",
        week_start=week_start,
        week_end=week_end,
        tasks=task_lines,
        busy_blocks=busy_lines,
        working_hours=WORKING_HOURS_HINT,
        context_hint=f"\nADDITIONAL CONTEXT FROM THE USER: {hint}\n" if hint else "",
    )


def _extract_json(text: str) -> Any | None:
    """Pull a JSON value out of a model response.

    Tolerates ```json fences, leading/trailing prose and a bare array (when
    the model skips the {"suggestions": ...} wrapper).
    """
    if not text:
        return None
    cleaned = text.strip()
    # Strip a single outer markdown fence (```json ... ``` or ``` ... ```).
    fence = re.match(r"^```(?:json|JSON)?\s*\n?(.*?)\n?\s*```$", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1).strip()
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        pass
    # Messy output: take the outermost {...} or [...] block.
    for pattern in (r"\{.*\}", r"\[.*\]"):
        match = re.search(pattern, cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except (json.JSONDecodeError, ValueError):
                continue
    return None


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value.strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_time(value: Any) -> time | None:
    if not isinstance(value, str):
        return None
    match = _TIME_RE.match(value.strip())
    if not match:
        return None
    hour, minute, second = int(match.group(1)), int(match.group(2)), int(match.group(3) or 0)
    if hour > 23 or minute > 59 or second > 59:
        return None
    return time(hour, minute, second)


def _parse_block(block: dict, tz: ZoneInfo) -> tuple[datetime, datetime] | None:
    """Normalize one busy block into an aware [start, end) interval.

    Naive datetimes are interpreted in the user's timezone; aware ones keep
    their offset. A missing/unparseable end defaults to start + 60min so the
    block still excludes its slot.
    """
    if not isinstance(block, dict):
        return None
    start_raw, end_raw = block.get("start"), block.get("end")
    if not isinstance(start_raw, str):
        return None
    try:
        start = datetime.fromisoformat(start_raw.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if start.tzinfo is None:
        start = start.replace(tzinfo=tz)

    end: datetime | None = None
    if isinstance(end_raw, str) and end_raw.strip():
        try:
            end = datetime.fromisoformat(end_raw.strip().replace("Z", "+00:00"))
            if end.tzinfo is None:
                end = end.replace(tzinfo=tz)
        except ValueError:
            end = None
    if end is None or end <= start:
        end = start + timedelta(minutes=60)
    return start, end


def _overlaps(start: datetime, end: datetime, intervals: list[tuple[datetime, datetime]]) -> bool:
    return any(start < busy_end and end > busy_start for busy_start, busy_end in intervals)


def parse_plan_response(
    raw: str,
    tasks: list[dict],
    busy_blocks: list[dict],
    week_start: str,
    week_end: str,
    timezone: str,
) -> list[dict]:
    """Validate LLM output into clean suggestion dicts.

    A suggestion survives only if: its task_id was in the request (and hasn't
    already been placed), date is inside [week_start, week_end], times parse
    and end > start, and the resulting interval overlaps no busy block and no
    already-accepted suggestion. Everything else is silently dropped.
    """
    window_start = _parse_date(week_start)
    window_end = _parse_date(week_end)
    if window_start is None or window_end is None:
        return []
    tz = _local_zone(timezone)

    durations = {
        t["id"]: t.get("duration_minutes") or DEFAULT_DURATION_MINUTES for t in tasks if isinstance(t.get("id"), int)
    }
    busy = [parsed for b in busy_blocks if (parsed := _parse_block(b, tz)) is not None]

    data = _extract_json(raw)
    if isinstance(data, dict):
        suggestions = data.get("suggestions")
    elif isinstance(data, list):
        suggestions = data  # model returned a bare array
    else:
        suggestions = None
    if not isinstance(suggestions, list):
        return []

    accepted: list[dict] = []
    placed: list[tuple[datetime, datetime]] = []
    seen_ids: set[int] = set()
    for s in suggestions:
        if not isinstance(s, dict):
            continue
        task_id = s.get("task_id")
        if not isinstance(task_id, int) or isinstance(task_id, bool):
            continue
        if task_id not in durations or task_id in seen_ids:
            continue
        day = _parse_date(s.get("date"))
        start_t = _parse_time(s.get("start_time"))
        if day is None or start_t is None or not (window_start <= day <= window_end):
            continue
        start_dt = datetime.combine(day, start_t, tzinfo=tz)
        end_t = _parse_time(s.get("end_time")) if s.get("end_time") else None
        if end_t is not None:
            end_dt = datetime.combine(day, end_t, tzinfo=tz)
            if end_dt <= start_dt:
                continue
        else:
            end_dt = start_dt + timedelta(minutes=durations[task_id])
        if _overlaps(start_dt, end_dt, busy) or _overlaps(start_dt, end_dt, placed):
            continue
        seen_ids.add(task_id)
        placed.append((start_dt, end_dt))
        accepted.append(
            {
                "task_id": task_id,
                "date": day.isoformat(),
                "start_time": start_dt.strftime("%H:%M"),
                "end_time": end_dt.strftime("%H:%M"),
                "rationale": str(s.get("rationale") or "")[:300],
            }
        )
    return accepted
