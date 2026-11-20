"""``joidy notes`` — note capture and management against ``/notes``."""

from __future__ import annotations

import sys
from typing import Annotated

import typer

from .. import client as client_mod
from .. import output
from ..options import ApiUrlOpt, Flags, JQOpt, JSONOpt, TokenOpt, YesOpt

notes_app = typer.Typer(help="Create, list, edit and delete notes.", no_args_is_help=True)


def _require_title(title: str | None) -> str:
    if title is not None:
        return title
    if sys.stdin.isatty():
        return typer.prompt("Title")
    output.die("--title is required when stdin is not a TTY", output.EXIT_USAGE)
    raise AssertionError("unreachable")


def _read_content(content: str | None) -> str:
    if content == "-":
        return sys.stdin.read()
    if content is not None:
        return content
    if sys.stdin.isatty() and sys.stdout.isatty():
        return typer.prompt("Content", default="", show_default=False)
    return ""


@notes_app.command("ls")
def ls(
    ctx: typer.Context,
    tag: Annotated[str | None, typer.Option("--tag", help="Filter by tag name.")] = None,
    source_path: Annotated[str | None, typer.Option("--source-path", help="Filter by vault path.")] = None,
    limit: Annotated[int, typer.Option("--limit", min=1, max=1000)] = 100,
    skip: Annotated[int, typer.Option("--skip", min=0)] = 0,
    json: JSONOpt = False,
    jq: JQOpt = None,
    yes: YesOpt = False,
    api_url: ApiUrlOpt = None,
    token: TokenOpt = None,
) -> None:
    """List notes (newest first)."""
    flags = Flags.make(ctx, json=json, jq=jq, yes=yes, api_url=api_url, token=token)
    params: dict = {"limit": limit, "skip": skip}
    if tag:
        params["tag"] = tag
    if source_path:
        params["source_path"] = source_path
    flags.emit(client_mod.call(flags.client(), "GET", "/notes/", params=params))


@notes_app.command("new")
def new(
    ctx: typer.Context,
    title: Annotated[str | None, typer.Option("--title", "-t", help="Note title.")] = None,
    content: Annotated[
        str | None,
        typer.Option("--content", "-c", help="Note body; '-' reads it from stdin."),
    ] = None,
    tag: Annotated[list[str] | None, typer.Option("--tag", help="Tag to attach (repeatable).")] = None,
    json: JSONOpt = False,
    jq: JQOpt = None,
    yes: YesOpt = False,
    api_url: ApiUrlOpt = None,
    token: TokenOpt = None,
) -> None:
    """Create a note. Example: cat note.md | joidy notes new --title T --content - --json"""
    flags = Flags.make(ctx, json=json, jq=jq, yes=yes, api_url=api_url, token=token)
    body = {
        "title": _require_title(title),
        "content": _read_content(content),
        "tags": tag or [],
        "source": "api",
    }
    flags.emit(client_mod.call(flags.client(), "POST", "/notes/", body=body))


@notes_app.command("get")
def get(
    ctx: typer.Context,
    note_id: Annotated[int, typer.Argument(help="Note ID.")],
    json: JSONOpt = False,
    jq: JQOpt = None,
    yes: YesOpt = False,
    api_url: ApiUrlOpt = None,
    token: TokenOpt = None,
) -> None:
    """Fetch a single note by ID."""
    flags = Flags.make(ctx, json=json, jq=jq, yes=yes, api_url=api_url, token=token)
    flags.emit(client_mod.call(flags.client(), "GET", f"/notes/{note_id}"))


@notes_app.command("edit")
def edit(
    ctx: typer.Context,
    note_id: Annotated[int, typer.Argument(help="Note ID.")],
    title: Annotated[str | None, typer.Option("--title", "-t")] = None,
    content: Annotated[str | None, typer.Option("--content", "-c", help="New body; '-' reads stdin.")] = None,
    tag: Annotated[list[str] | None, typer.Option("--tag", help="Replace tag set (repeatable).")] = None,
    json: JSONOpt = False,
    jq: JQOpt = None,
    yes: YesOpt = False,
    api_url: ApiUrlOpt = None,
    token: TokenOpt = None,
) -> None:
    """Update a note's title, content, and/or tags."""
    flags = Flags.make(ctx, json=json, jq=jq, yes=yes, api_url=api_url, token=token)
    body: dict = {}
    if title is not None:
        body["title"] = title
    if content is not None:
        body["content"] = sys.stdin.read() if content == "-" else content
    if tag is not None:
        body["tags"] = tag
    if not body:
        output.die("nothing to update — pass --title, --content or --tag", output.EXIT_USAGE)
    flags.emit(client_mod.call(flags.client(), "PUT", f"/notes/{note_id}", body=body))


@notes_app.command("rm")
def rm(
    ctx: typer.Context,
    note_id: Annotated[int, typer.Argument(help="Note ID.")],
    json: JSONOpt = False,
    jq: JQOpt = None,
    yes: YesOpt = False,
    api_url: ApiUrlOpt = None,
    token: TokenOpt = None,
) -> None:
    """Delete a note (asks for confirmation unless --yes)."""
    flags = Flags.make(ctx, json=json, jq=jq, yes=yes, api_url=api_url, token=token)
    output.confirm(f"Delete note {note_id}?", yes=flags.yes)
    client_mod.call(flags.client(), "DELETE", f"/notes/{note_id}")
    flags.emit({"status": "deleted", "id": note_id})
