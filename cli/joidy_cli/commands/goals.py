"""``joidy goals`` — goal management against ``/goals``.

Temporality goals (DAILY/WEEKLY/MONTHLY/ANNUAL) are stored as one row per
period *instance*: ``joidy goals done <id>`` completes the current period
instance, and the API spawns the next instance automatically for
ROLLOVER/SNOWBALL fail configs.
"""

from __future__ import annotations

import sys
from typing import Annotated

import typer

from .. import client as client_mod
from .. import output
from ..options import ApiUrlOpt, Flags, JQOpt, JSONOpt, TokenOpt, YesOpt

goals_app = typer.Typer(help="Create, list, complete and fail goals.", no_args_is_help=True)

TEMPORALITIES = ["ONEOFF", "DAILY", "WEEKLY", "MONTHLY", "ANNUAL"]
CONTEXTS = ["ANY", "MORNING", "NIGHT"]
MEASUREMENTS = ["COUNT", "BOOLEAN", "PERCENT"]
FAIL_CONFIGS = ["STATIC", "ROLLOVER", "SNOWBALL"]
STATES = ["INBOX", "ACTIVE", "COMPLETED", "FAILED", "PAUSED", "CANCELLED"]


def _choice(name: str, value: str | None, allowed: list[str]) -> str | None:
    if value is None:
        return None
    v = value.upper()
    if v not in allowed:
        output.die(f"invalid --{name} '{value}' (allowed: {', '.join(allowed)})", output.EXIT_USAGE)
    return v


def _require_title(title: str | None) -> str:
    if title is not None:
        return title
    if sys.stdin.isatty():
        return typer.prompt("Title")
    output.die("--title is required when stdin is not a TTY", output.EXIT_USAGE)
    raise AssertionError("unreachable")


@goals_app.command("ls")
def ls(
    ctx: typer.Context,
    state: Annotated[str | None, typer.Option("--state", help=f"Filter by state: {', '.join(STATES)}.")] = None,
    context: Annotated[str | None, typer.Option("--context", help=f"Filter by context: {', '.join(CONTEXTS)}.")] = None,
    limit: Annotated[int, typer.Option("--limit", min=1, max=1000)] = 100,
    skip: Annotated[int, typer.Option("--skip", min=0)] = 0,
    json: JSONOpt = False,
    jq: JQOpt = None,
    yes: YesOpt = False,
    api_url: ApiUrlOpt = None,
    token: TokenOpt = None,
) -> None:
    """List goals. ACTIVE rows are the current period instances."""
    flags = Flags.make(ctx, json=json, jq=jq, yes=yes, api_url=api_url, token=token)
    params: dict = {"limit": limit, "skip": skip}
    if state:
        params["state"] = _choice("state", state, STATES)
    if context:
        params["context"] = _choice("context", context, CONTEXTS)
    flags.emit(client_mod.call(flags.client(), "GET", "/goals/", params=params))


@goals_app.command("new")
def new(
    ctx: typer.Context,
    title: Annotated[str | None, typer.Option("--title", "-t", help="Goal title.")] = None,
    description: Annotated[str | None, typer.Option("--description", "-d")] = None,
    temporality: Annotated[
        str, typer.Option("--temporality", help=f"Period type: {', '.join(TEMPORALITIES)}.")
    ] = "ONEOFF",
    context: Annotated[str, typer.Option("--context", help=f"Energy slot: {', '.join(CONTEXTS)}.")] = "ANY",
    measurement: Annotated[
        str, typer.Option("--measurement", help=f"Progress type: {', '.join(MEASUREMENTS)}.")
    ] = "COUNT",
    target: Annotated[float, typer.Option("--target", help="Target value for the period.")] = 1.0,
    fail_config: Annotated[
        str, typer.Option("--fail-config", help=f"On expiry: {', '.join(FAIL_CONFIGS)}.")
    ] = "STATIC",
    priority: Annotated[int, typer.Option("--priority", help="Higher floats to the top (0-99).")] = 0,
    note_id: Annotated[int | None, typer.Option("--note-id", help="Link an existing note.")] = None,
    tag_id: Annotated[
        int | None, typer.Option("--tag-id", help="Link a tag (COUNT goals measure tagged notes).")
    ] = None,
    parent_id: Annotated[int | None, typer.Option("--parent-id", help="Parent goal ID.")] = None,
    json: JSONOpt = False,
    jq: JQOpt = None,
    yes: YesOpt = False,
    api_url: ApiUrlOpt = None,
    token: TokenOpt = None,
) -> None:
    """Create a goal. Temporality goals create the current period instance."""
    flags = Flags.make(ctx, json=json, jq=jq, yes=yes, api_url=api_url, token=token)
    body: dict = {
        "title": _require_title(title),
        "temporality": _choice("temporality", temporality, TEMPORALITIES),
        "context": _choice("context", context, CONTEXTS),
        "measurement_type": _choice("measurement", measurement, MEASUREMENTS),
        "target_value": target,
        "fail_config": _choice("fail-config", fail_config, FAIL_CONFIGS),
        "priority": priority,
    }
    if description is not None:
        body["description"] = description
    if note_id is not None:
        body["note_id"] = note_id
    if tag_id is not None:
        body["tag_id"] = tag_id
    if parent_id is not None:
        body["parent_id"] = parent_id
    flags.emit(client_mod.call(flags.client(), "POST", "/goals/", body=body))


@goals_app.command("get")
def get(
    ctx: typer.Context,
    goal_id: Annotated[int, typer.Argument(help="Goal ID.")],
    json: JSONOpt = False,
    jq: JQOpt = None,
    yes: YesOpt = False,
    api_url: ApiUrlOpt = None,
    token: TokenOpt = None,
) -> None:
    """Fetch a single goal (period instance) by ID."""
    flags = Flags.make(ctx, json=json, jq=jq, yes=yes, api_url=api_url, token=token)
    flags.emit(client_mod.call(flags.client(), "GET", f"/goals/{goal_id}"))


@goals_app.command("done")
def done(
    ctx: typer.Context,
    goal_id: Annotated[int, typer.Argument(help="Goal ID (the current period instance).")],
    json: JSONOpt = False,
    jq: JQOpt = None,
    yes: YesOpt = False,
    api_url: ApiUrlOpt = None,
    token: TokenOpt = None,
) -> None:
    """Mark a goal complete. For temporality goals this completes the current period instance."""
    flags = Flags.make(ctx, json=json, jq=jq, yes=yes, api_url=api_url, token=token)
    flags.emit(client_mod.call(flags.client(), "POST", f"/goals/{goal_id}/complete"))


@goals_app.command("fail")
def fail(
    ctx: typer.Context,
    goal_id: Annotated[int, typer.Argument(help="Goal ID (the current period instance).")],
    json: JSONOpt = False,
    jq: JQOpt = None,
    yes: YesOpt = False,
    api_url: ApiUrlOpt = None,
    token: TokenOpt = None,
) -> None:
    """Mark the current period instance as failed."""
    flags = Flags.make(ctx, json=json, jq=jq, yes=yes, api_url=api_url, token=token)
    flags.emit(client_mod.call(flags.client(), "POST", f"/goals/{goal_id}/fail"))


@goals_app.command("rm")
def rm(
    ctx: typer.Context,
    goal_id: Annotated[int, typer.Argument(help="Goal ID.")],
    json: JSONOpt = False,
    jq: JQOpt = None,
    yes: YesOpt = False,
    api_url: ApiUrlOpt = None,
    token: TokenOpt = None,
) -> None:
    """Delete a goal (asks for confirmation unless --yes)."""
    flags = Flags.make(ctx, json=json, jq=jq, yes=yes, api_url=api_url, token=token)
    output.confirm(f"Delete goal {goal_id}?", yes=flags.yes)
    client_mod.call(flags.client(), "DELETE", f"/goals/{goal_id}")
    flags.emit({"status": "deleted", "id": goal_id})
