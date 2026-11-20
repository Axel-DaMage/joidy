"""Output and exit-code conventions shared by every command.

Exit codes (stable, documented — see ``joidy commands --json``):

- ``0`` success
- ``1`` generic error (including 4xx responses not mapped below)
- ``2`` usage error (missing/invalid arguments, API 400/422)
- ``3`` authentication required or rejected (401/403)
- ``4`` resource not found (404)
- ``5`` server error or API unreachable

Output rules:

- ``--json`` always emits the raw API payload as pretty JSON.
- ``--jq <expr>`` applies a JMESPath expression (like ``aws --query`` /
  ``gh --jq``) and emits the result as JSON.
- When stdout is not a TTY the output defaults to JSON so agents never
  scrape human-formatted text; pass ``--no-json`` behaviour is not needed —
  TTY sessions get a compact human rendering automatically.
- All errors go to stderr; stdout stays machine-readable.
"""

from __future__ import annotations

import json as _json
import sys
from typing import Any

import typer

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_AUTH = 3
EXIT_NOT_FOUND = 4
EXIT_SERVER = 5

EXIT_CODES: dict[str, str] = {
    "0": "success",
    "1": "generic error / unexpected API failure",
    "2": "usage error (bad arguments, API 400/422)",
    "3": "authentication required or rejected (401/403)",
    "4": "resource not found (404)",
    "5": "server error or API unreachable",
}

_MAX_COLS = 6
_MAX_WIDTH = 28


def is_interactive() -> bool:
    """True only when both stdin and stdout are real terminals."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def err(message: str) -> None:
    typer.echo(f"joidy: error: {message}", err=True)


def die(message: str, code: int = EXIT_ERROR) -> None:
    """Print a structured error on stderr and exit with a stable code."""
    err(message)
    raise typer.Exit(code)


def emit(data: Any, *, json_mode: bool = False, jq: str | None = None) -> None:
    """Render ``data`` per the output rules above."""
    if jq is not None:
        import jmespath
        from jmespath import exceptions as jmes_exceptions

        try:
            data = jmespath.search(jq, data)
        except jmes_exceptions.JMESPathError as exc:
            die(f"invalid --jq expression: {exc}", EXIT_USAGE)
        json_mode = True
    if json_mode or not sys.stdout.isatty():
        typer.echo(_json.dumps(data, indent=2, ensure_ascii=False, default=str))
    else:
        _human(data)


def confirm(prompt: str, *, yes: bool = False) -> None:
    """Gate a destructive action behind a confirmation.

    ``--yes`` skips the prompt. When stdin is not a TTY the prompt cannot be
    shown, so the operation aborts with a usage error unless ``--yes`` was
    given — same contract as ``gh``/``vercel``.
    """
    if yes:
        return
    if not sys.stdin.isatty():
        die("confirmation required; pass --yes in non-interactive mode", EXIT_USAGE)
    if not typer.confirm(prompt):
        die("aborted", EXIT_ERROR)


def _fmt(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return _json.dumps(value, ensure_ascii=False, default=str)
    if value is None:
        return ""
    return str(value)


def _human(data: Any) -> None:
    if data is None:
        return
    if isinstance(data, list):
        if not data:
            typer.echo("(no results)")
            return
        if all(isinstance(item, dict) for item in data):
            _table(data)
        else:
            for item in data:
                typer.echo(_fmt(item))
    elif isinstance(data, dict):
        width = max((len(key) for key in data), default=0)
        for key, value in data.items():
            typer.echo(f"{key:<{width}} : {_fmt(value)}")
    else:
        typer.echo(_fmt(data))


def _table(rows: list[dict[str, Any]]) -> None:
    keys: list[str] = []
    for row in rows[:20]:
        for key in row:
            if key not in keys:
                keys.append(key)
    keys = keys[:_MAX_COLS]

    def clip(value: str) -> str:
        return value if len(value) <= _MAX_WIDTH else value[: _MAX_WIDTH - 1] + "…"

    widths = {key: min(_MAX_WIDTH, max([len(key)] + [len(_fmt(row.get(key))) for row in rows[:50]])) for key in keys}
    header = "  ".join(key.ljust(widths[key]) for key in keys)
    typer.echo(header)
    typer.echo("  ".join("-" * widths[key] for key in keys))
    for row in rows:
        typer.echo("  ".join(clip(_fmt(row.get(key))).ljust(widths[key]) for key in keys))
