"""Interactive picker — ``joidy`` with no arguments on a TTY.

A numbered, guided menu covering quick actions for notes, goals and
streaks plus stack status and auth. All API failures are reported inline
and the loop resumes, so a 401 simply means "run login from the menu".
"""

from __future__ import annotations

from typing import Any

import typer

from . import client as client_mod
from . import config, output, stack
from .commands.auth import do_login

MENU = """\
== Joidy ==
  Notes    1) capture    2) list
  Goals    3) new        4) list      5) complete
  Streaks  6) check in   7) new       8) list
  Stack    9) status
  Auth     l) login      s) status
           q) quit"""


def run() -> None:
    """Main interactive loop. Returns when the user quits."""
    api = client_mod.create()
    typer.echo(MENU)
    while True:
        try:
            choice = _input("joidy> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            typer.echo("")
            return
        if choice in {"q", "quit", "exit", ""}:
            return
        try:
            if not _dispatch(choice, api):
                typer.echo(f"unknown choice '{choice}' — pick a number, l, s or q")
        except client_mod.ApiError as exc:
            output.err(str(exc))
        except (EOFError, KeyboardInterrupt):
            typer.echo("")
            return


def _dispatch(choice: str, api: client_mod.ApiClient) -> bool:
    if choice == "1":
        _capture_note(api)
    elif choice == "2":
        _list(api, "/notes/", ["id", "title", "tags"])
    elif choice == "3":
        _new_goal(api)
    elif choice == "4":
        _list(api, "/goals/", ["id", "title", "state", "temporality", "current_value", "target_value"])
    elif choice == "5":
        _complete_goal(api)
    elif choice == "6":
        _checkin(api)
    elif choice == "7":
        _new_streak(api)
    elif choice == "8":
        _list(api, "/personal-streaks/", ["id", "name", "current_streak", "today_checked"])
    elif choice == "9":
        stack.run(["status"])
    elif choice == "l":
        _login(api)
    elif choice == "s":
        _auth_status(api)
    elif choice == "?":
        typer.echo(MENU)
    else:
        return False
    return True


def _input(prompt: str) -> str:
    """Prompt for a line of input (patch point for tests/future fzf)."""
    return input(prompt)


def _pick(items: list[dict[str, Any]], label: str, display: str) -> dict[str, Any] | None:
    if not items:
        typer.echo(f"(no {label})")
        return None
    for idx, item in enumerate(items, 1):
        typer.echo(f" {idx:>2}) {item.get(display, item.get('id'))}  [id={item.get('id')}]")
    raw = _input(f"pick {label} # (empty cancels): ").strip()
    if not raw:
        return None
    try:
        idx = int(raw)
    except ValueError:
        # Also accept a raw resource id.
        for item in items:
            if str(item.get("id")) == raw:
                return item
        output.err(f"invalid selection '{raw}'")
        return None
    if not 1 <= idx <= len(items):
        output.err(f"out of range '{raw}'")
        return None
    return items[idx - 1]


def _capture_note(api: client_mod.ApiClient) -> None:
    title = _input("title: ").strip()
    if not title:
        output.err("title cannot be empty")
        return
    typer.echo("content (end with a single '.' line):")
    lines: list[str] = []
    while True:
        line = _input("... ")
        if line == ".":
            break
        lines.append(line)
    note = api.request("POST", "/notes/", body={"title": title, "content": "\n".join(lines), "source": "api"})
    typer.echo(f"created note id={note.get('id')} — {note.get('title')}")


def _new_goal(api: client_mod.ApiClient) -> None:
    title = _input("title: ").strip()
    if not title:
        output.err("title cannot be empty")
        return
    temporality = (
        _input("temporality [ONEOFF/DAILY/WEEKLY/MONTHLY/ANNUAL] (default ONEOFF): ").strip().upper() or "ONEOFF"
    )
    target = _input("target value (default 1): ").strip() or "1"
    goal = api.request(
        "POST",
        "/goals/",
        body={"title": title, "temporality": temporality, "target_value": float(target)},
    )
    typer.echo(f"created goal id={goal.get('id')} — {goal.get('title')} [{goal.get('temporality')}]")


def _complete_goal(api: client_mod.ApiClient) -> None:
    goals = api.request("GET", "/goals/", params={"state": "ACTIVE", "limit": 200}) or []
    goal = _pick(goals, "goal", "title")
    if goal is None:
        return
    result = api.request("POST", f"/goals/{goal['id']}/complete")
    gami = (result or {}).get("gamification") or {}
    xp = gami.get("xp_awarded") or gami.get("xp_gained") or ""
    typer.echo(f"completed goal {goal['id']} — {goal.get('title')}" + (f" (+{xp} XP)" if xp else ""))


def _checkin(api: client_mod.ApiClient) -> None:
    streaks = api.request("GET", "/personal-streaks/", params={"include_history": False}) or []
    streak = _pick(streaks, "streak", "name")
    if streak is None:
        return
    note = _input("note (optional): ").strip()
    result = api.request("POST", f"/personal-streaks/{streak['id']}/checkin", body={"note": note} if note else {})
    typer.echo(f"checked in {streak.get('name')} — streak: {result.get('current_streak')}")


def _new_streak(api: client_mod.ApiClient) -> None:
    name = _input("name: ").strip()
    if not name:
        output.err("name cannot be empty")
        return
    streak = api.request("POST", "/personal-streaks/", body={"name": name})
    typer.echo(f"created streak id={streak.get('id')} — {streak.get('name')}")


def _list(api: client_mod.ApiClient, path: str, columns: list[str]) -> None:
    items = api.request("GET", path) or []
    if not items:
        typer.echo("(nothing found)")
        return
    for item in items[:20]:
        row = "  ".join(str(item.get(col, "")) for col in columns)
        typer.echo(row)
    if len(items) > 20:
        typer.echo(f"… and {len(items) - 20} more")


def _login(api: client_mod.ApiClient) -> None:
    username = _input(f"username [{'user'}]: ").strip() or "user"
    password = typer.prompt("password", hide_input=True)
    token = do_login(api, username, password)
    path = config.store_token(token, api.base_url)
    api.token = token
    typer.echo(f"logged in — token stored in {path}")


def _auth_status(api: client_mod.ApiClient) -> None:
    _token, source = config.get_token()
    typer.echo(f"api_url={api.base_url}  token_source={source}")
    try:
        probe = api.request("GET", "/auth/status")
        typer.echo(f"reachable=yes  auth_enabled={probe.get('enabled')}")
    except client_mod.ApiError:
        typer.echo("reachable=no")


def is_interactive() -> bool:
    return output.is_interactive()
