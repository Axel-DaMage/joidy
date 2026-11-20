"""``joidy streaks`` — personal streaks against ``/personal-streaks``."""

from __future__ import annotations

import sys
from typing import Annotated

import typer

from .. import client as client_mod
from .. import output
from ..options import ApiUrlOpt, Flags, JQOpt, JSONOpt, TokenOpt, YesOpt

streaks_app = typer.Typer(help="Create, check in, freeze and inspect personal streaks.", no_args_is_help=True)

FREQUENCIES = ["daily", "weekly", "monthly", "every_n"]


def _require_name(name: str | None) -> str:
    if name is not None:
        return name
    if sys.stdin.isatty():
        return typer.prompt("Name")
    output.die("--name is required when stdin is not a TTY", output.EXIT_USAGE)
    raise AssertionError("unreachable")


@streaks_app.command("ls")
def ls(
    ctx: typer.Context,
    category: Annotated[str | None, typer.Option("--category", help="Filter by category.")] = None,
    archived: Annotated[bool, typer.Option("--archived", help="Include archived streaks.")] = False,
    limit: Annotated[int, typer.Option("--limit", min=1, max=200)] = 50,
    json: JSONOpt = False,
    jq: JQOpt = None,
    yes: YesOpt = False,
    api_url: ApiUrlOpt = None,
    token: TokenOpt = None,
) -> None:
    """List streaks with current/best run length and today's check-in state."""
    flags = Flags.make(ctx, json=json, jq=jq, yes=yes, api_url=api_url, token=token)
    params: dict = {"limit": limit, "include_archived": archived}
    if category:
        params["category"] = category
    flags.emit(client_mod.call(flags.client(), "GET", "/personal-streaks/", params=params))


@streaks_app.command("new")
def new(
    ctx: typer.Context,
    name: Annotated[str | None, typer.Option("--name", "-n", help="Streak name.")] = None,
    emoji: Annotated[str, typer.Option("--emoji")] = "🔥",
    category: Annotated[str, typer.Option("--category")] = "general",
    frequency: Annotated[str, typer.Option("--frequency", help=f"One of: {', '.join(FREQUENCIES)}.")] = "daily",
    frequency_days: Annotated[
        int, typer.Option("--frequency-days", min=1, max=365, help="Interval for every_n frequency.")
    ] = 1,
    description: Annotated[str | None, typer.Option("--description", "-d")] = None,
    start_date: Annotated[str | None, typer.Option("--start-date", help="YYYY-MM-DD.")] = None,
    target_date: Annotated[str | None, typer.Option("--target-date", help="YYYY-MM-DD.")] = None,
    offset: Annotated[int, typer.Option("--offset", min=0, max=36500, help="Existing streak days to seed.")] = 0,
    freeze_count: Annotated[int, typer.Option("--freeze-count", min=0, max=30, help="Freezes granted.")] = 0,
    snowball: Annotated[bool, typer.Option("--snowball", help="Enable snowball mode.")] = False,
    json: JSONOpt = False,
    jq: JQOpt = None,
    yes: YesOpt = False,
    api_url: ApiUrlOpt = None,
    token: TokenOpt = None,
) -> None:
    """Create a streak."""
    flags = Flags.make(ctx, json=json, jq=jq, yes=yes, api_url=api_url, token=token)
    if frequency not in FREQUENCIES:
        output.die(f"invalid --frequency '{frequency}' (allowed: {', '.join(FREQUENCIES)})", output.EXIT_USAGE)
    body: dict = {
        "name": _require_name(name),
        "emoji": emoji,
        "category": category,
        "frequency": frequency,
        "frequency_days": frequency_days,
        "offset": offset,
        "freeze_count": freeze_count,
        "snowball_mode": snowball,
    }
    if description is not None:
        body["description"] = description
    if start_date is not None:
        body["start_date"] = start_date
    if target_date is not None:
        body["target_date"] = target_date
    flags.emit(client_mod.call(flags.client(), "POST", "/personal-streaks/", body=body))


@streaks_app.command("checkin")
def checkin(
    ctx: typer.Context,
    streak_id: Annotated[int, typer.Argument(help="Streak ID.")],
    note: Annotated[str | None, typer.Option("--note", "-n", help="Check-in note.")] = None,
    mood: Annotated[int | None, typer.Option("--mood", min=1, max=5, help="Mood 1-5.")] = None,
    date: Annotated[str | None, typer.Option("--date", help="Check date YYYY-MM-DD (default: today).")] = None,
    json: JSONOpt = False,
    jq: JQOpt = None,
    yes: YesOpt = False,
    api_url: ApiUrlOpt = None,
    token: TokenOpt = None,
) -> None:
    """Check in a streak for today (or --date)."""
    flags = Flags.make(ctx, json=json, jq=jq, yes=yes, api_url=api_url, token=token)
    body: dict = {}
    if note is not None:
        body["note"] = note
    if mood is not None:
        body["mood"] = mood
    if date is not None:
        body["check_date"] = date
    flags.emit(client_mod.call(flags.client(), "POST", f"/personal-streaks/{streak_id}/checkin", body=body))


@streaks_app.command("uncheckin")
def uncheckin(
    ctx: typer.Context,
    streak_id: Annotated[int, typer.Argument(help="Streak ID.")],
    json: JSONOpt = False,
    jq: JQOpt = None,
    yes: YesOpt = False,
    api_url: ApiUrlOpt = None,
    token: TokenOpt = None,
) -> None:
    """Undo today's check-in."""
    flags = Flags.make(ctx, json=json, jq=jq, yes=yes, api_url=api_url, token=token)
    flags.emit(client_mod.call(flags.client(), "DELETE", f"/personal-streaks/{streak_id}/checkin"))


@streaks_app.command("freeze")
def freeze(
    ctx: typer.Context,
    streak_id: Annotated[int, typer.Argument(help="Streak ID.")],
    json: JSONOpt = False,
    jq: JQOpt = None,
    yes: YesOpt = False,
    api_url: ApiUrlOpt = None,
    token: TokenOpt = None,
) -> None:
    """Spend a freeze to protect the streak for today."""
    flags = Flags.make(ctx, json=json, jq=jq, yes=yes, api_url=api_url, token=token)
    flags.emit(client_mod.call(flags.client(), "POST", f"/personal-streaks/{streak_id}/freeze"))


@streaks_app.command("history")
def history(
    ctx: typer.Context,
    streak_id: Annotated[int, typer.Argument(help="Streak ID.")],
    days: Annotated[int, typer.Option("--days", min=7, max=365, help="Look-back window.")] = 90,
    json: JSONOpt = False,
    jq: JQOpt = None,
    yes: YesOpt = False,
    api_url: ApiUrlOpt = None,
    token: TokenOpt = None,
) -> None:
    """Show the check-in history for a streak."""
    flags = Flags.make(ctx, json=json, jq=jq, yes=yes, api_url=api_url, token=token)
    flags.emit(client_mod.call(flags.client(), "GET", f"/personal-streaks/{streak_id}/history", params={"days": days}))


@streaks_app.command("rm")
def rm(
    ctx: typer.Context,
    streak_id: Annotated[int, typer.Argument(help="Streak ID.")],
    json: JSONOpt = False,
    jq: JQOpt = None,
    yes: YesOpt = False,
    api_url: ApiUrlOpt = None,
    token: TokenOpt = None,
) -> None:
    """Delete a streak (asks for confirmation unless --yes)."""
    flags = Flags.make(ctx, json=json, jq=jq, yes=yes, api_url=api_url, token=token)
    output.confirm(f"Delete streak {streak_id}?", yes=flags.yes)
    client_mod.call(flags.client(), "DELETE", f"/personal-streaks/{streak_id}")
    flags.emit({"status": "deleted", "id": streak_id})
