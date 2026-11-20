"""``joidy`` — interactive terminal client and agent-native interface.

Two operating modes:

- **Interactive** (humans): bare ``joidy`` on a TTY opens a guided picker.
- **Script** (agents): every command accepts flags for all inputs, emits
  JSON on stdout (default when piped), writes errors to stderr and never
  blocks on prompts when stdin/stdout is not a TTY.

Stack management (``up/down/status/logs/...``) is delegated to
``scripts/joidy.sh`` — see ``joidy_cli.stack``.
"""

from __future__ import annotations

import typer

from . import __version__, interactive, output, stack
from .commands.auth import auth_app
from .commands.goals import goals_app
from .commands.meta import commands as _commands_cmd
from .commands.meta import completion as _completion_cmd
from .commands.notes import notes_app
from .commands.streaks import streaks_app

_PASSTHROUGH = {"allow_extra_args": True, "ignore_unknown_options": True}

app = typer.Typer(
    name="joidy",
    help=(
        "Joidy — interactive terminal client and agent-native interface. "
        "Run bare `joidy` on a TTY for the interactive picker; every command "
        "supports --json, --jq and --yes for agents."
    ),
    invoke_without_command=True,
    no_args_is_help=False,
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
    pretty_exceptions_enable=False,
)

app.add_typer(auth_app, name="auth")
app.add_typer(notes_app, name="notes")
app.add_typer(goals_app, name="goals")
app.add_typer(streaks_app, name="streaks")

system_app = typer.Typer(help="Manage the Docker stack (delegated to scripts/joidy.sh).", no_args_is_help=True)
app.add_typer(system_app, name="system")

# Meta commands live at the top level: `joidy commands`, `joidy completion`.
app.command("commands")(_commands_cmd)
app.command("completion")(_completion_cmd)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"joidy {__version__}")
        raise typer.Exit()


@app.callback()
def _root(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Print version and exit.",
    ),
    json: bool = typer.Option(False, "--json", help="Emit raw JSON output.", hidden=True),
    jq: str = typer.Option(None, "--jq", help="JMESPath output filter.", hidden=True),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompts.", hidden=True),
    api_url: str = typer.Option(None, "--api-url", help="Joidy API base URL.", hidden=True),
    token: str = typer.Option(None, "--token", help="Bearer token.", hidden=True),
) -> None:
    ctx.obj = {"json": json, "jq": jq, "yes": yes, "api_url": api_url, "token": token}
    if ctx.invoked_subcommand is None:
        if interactive.is_interactive():
            interactive.run()
        else:
            typer.echo(ctx.get_help())
        raise typer.Exit()


def _stack_cmd(name: str):
    """Build a passthrough command forwarding `joidy <name>` to the stack CLI."""

    def _cmd(ctx: typer.Context) -> None:
        raise typer.Exit(stack.run([name, *ctx.args]))

    _cmd.__doc__ = f"Forward `joidy {name}` to the stack CLI (scripts/joidy.sh)."
    return _cmd


for _name in ("up", "down", "restart", "sleep", "wake", "logs"):
    app.command(_name, context_settings=_PASSTHROUGH)(_stack_cmd(_name))
    system_app.command(_name, context_settings=_PASSTHROUGH)(_stack_cmd(_name))


def _status_cmd(ctx: typer.Context) -> None:
    """Show stack status — JSON array with --json or when piped."""
    forwarded = [a for a in ctx.args if a != "--json"]
    json_flag = "--json" in ctx.args or (ctx.obj or {}).get("json", False)
    if json_flag or not output.is_interactive():
        stack.status_json()
        return
    raise typer.Exit(stack.run(["status", *forwarded]))


app.command("status", context_settings=_PASSTHROUGH)(_status_cmd)
system_app.command("status", context_settings=_PASSTHROUGH)(_status_cmd)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
