"""Meta commands: ``joidy commands`` and ``joidy completion``.

``joidy commands --json`` returns the full machine-readable command tree —
the CLI equivalent of MCP tool discovery, so an agent can enumerate the
capability surface without reading docs.
"""

from __future__ import annotations

import sys
from typing import Annotated, Any

import typer

from .. import __version__, output
from ..options import ApiUrlOpt, Flags, JQOpt, JSONOpt, TokenOpt, YesOpt
from ..output import EXIT_CODES

GLOBAL_OPTIONS = {
    "--json": "emit raw JSON output (default when stdout is not a TTY)",
    "--jq <expr>": "JMESPath filter applied to the output",
    "--yes / -y": "skip confirmation prompts (required for destructive ops when non-interactive)",
    "--api-url <url>": "override the Joidy API base URL",
    "--token <jwt>": "override the bearer token",
}

ENVIRONMENT = {
    "JOIDY_API_URL": "API base URL (default http://localhost:8000)",
    "JOIDY_TOKEN": "bearer token, overrides ~/.config/joidy/config.toml",
    "JOIDY_CONFIG_DIR": "override the config directory",
    "JOIDY_DIR": "project directory used for stack delegation",
    "JOIDY_STACK_CLI": "explicit path to the stack-management CLI",
}

COMMAND_TREE: list[dict[str, Any]] = [
    {
        "path": "auth login",
        "summary": "log in and store the JWT",
        "mutating": True,
        "options": ["--username", "--password|- (stdin)", "--save-url"],
    },
    {"path": "auth logout", "summary": "remove the stored token", "mutating": True, "options": []},
    {"path": "auth status", "summary": "API URL, token source and auth state", "mutating": False, "options": []},
    {
        "path": "notes ls",
        "summary": "list notes",
        "mutating": False,
        "options": ["--tag", "--source-path", "--limit", "--skip"],
    },
    {
        "path": "notes new",
        "summary": "create a note",
        "mutating": True,
        "options": ["--title", "--content|- (stdin)", "--tag*"],
    },
    {"path": "notes get <id>", "summary": "fetch one note", "mutating": False, "options": []},
    {
        "path": "notes edit <id>",
        "summary": "update title/content/tags",
        "mutating": True,
        "options": ["--title", "--content|- (stdin)", "--tag*"],
    },
    {"path": "notes rm <id>", "summary": "delete a note", "mutating": True, "confirm": True, "options": []},
    {
        "path": "goals ls",
        "summary": "list goals (ACTIVE rows are current period instances)",
        "mutating": False,
        "options": ["--state", "--context", "--limit", "--skip"],
    },
    {
        "path": "goals new",
        "summary": "create a goal / period instance",
        "mutating": True,
        "options": [
            "--title",
            "--description",
            "--temporality",
            "--context",
            "--measurement",
            "--target",
            "--fail-config",
            "--priority",
            "--note-id",
            "--tag-id",
            "--parent-id",
        ],
    },
    {"path": "goals get <id>", "summary": "fetch one goal", "mutating": False, "options": []},
    {"path": "goals done <id>", "summary": "complete the current period instance", "mutating": True, "options": []},
    {"path": "goals fail <id>", "summary": "fail the current period instance", "mutating": True, "options": []},
    {"path": "goals rm <id>", "summary": "delete a goal", "mutating": True, "confirm": True, "options": []},
    {
        "path": "streaks ls",
        "summary": "list streaks",
        "mutating": False,
        "options": ["--category", "--archived", "--limit"],
    },
    {
        "path": "streaks new",
        "summary": "create a streak",
        "mutating": True,
        "options": [
            "--name",
            "--emoji",
            "--category",
            "--frequency",
            "--frequency-days",
            "--description",
            "--start-date",
            "--target-date",
            "--offset",
            "--freeze-count",
            "--snowball",
        ],
    },
    {
        "path": "streaks checkin <id>",
        "summary": "check in today (or --date)",
        "mutating": True,
        "options": ["--note", "--mood", "--date"],
    },
    {"path": "streaks uncheckin <id>", "summary": "undo today's check-in", "mutating": True, "options": []},
    {"path": "streaks freeze <id>", "summary": "spend a freeze for today", "mutating": True, "options": []},
    {"path": "streaks history <id>", "summary": "check-in history", "mutating": False, "options": ["--days"]},
    {"path": "streaks rm <id>", "summary": "delete a streak", "mutating": True, "confirm": True, "options": []},
    {
        "path": "system up|down|restart|sleep|wake|status|logs",
        "summary": "manage the Docker stack (delegated to scripts/joidy.sh)",
        "mutating": True,
        "options": ["<args forwarded>"],
    },
    {
        "path": "up|down|restart|sleep|wake|status|logs",
        "summary": "stack shortcuts (same delegate as `system`)",
        "mutating": True,
        "options": ["<args forwarded>"],
    },
    {"path": "commands", "summary": "machine-readable command tree (this output)", "mutating": False, "options": []},
    {
        "path": "completion <shell>",
        "summary": "print completion script for bash|zsh|fish",
        "mutating": False,
        "options": [],
    },
]


def manifest() -> dict[str, Any]:
    return {
        "name": "joidy",
        "version": __version__,
        "description": "Interactive terminal client and agent-native interface for the Joidy API.",
        "global_options": GLOBAL_OPTIONS,
        "environment": ENVIRONMENT,
        "exit_codes": EXIT_CODES,
        "commands": COMMAND_TREE,
    }


def commands(
    ctx: typer.Context,
    json: JSONOpt = False,
    jq: JQOpt = None,
    yes: YesOpt = False,
    api_url: ApiUrlOpt = None,
    token: TokenOpt = None,
) -> None:
    """Print the machine-readable command tree for agent discovery."""
    flags = Flags.make(ctx, json=json, jq=jq, yes=yes, api_url=api_url, token=token)
    data = manifest()
    if flags.jq is None and not flags.json and sys.stdout.isatty():
        # Human rendering: one line per command path.
        for entry in COMMAND_TREE:
            typer.echo(f"{entry['path']:<44} {entry['summary']}")
        return
    flags.emit(data)


# Static completion surface — kept in sync with the groups registered in
# ``main.py``. Typer's vendored click has no completion machinery, so these
# are plain scripts generated from the command tree.
_TOP_LEVEL = "auth notes goals streaks system commands completion up down restart sleep wake status logs"
_SUBCOMMANDS = {
    "auth": "login logout status",
    "notes": "ls new get edit rm",
    "goals": "ls new get done fail rm",
    "streaks": "ls new checkin uncheckin freeze history rm",
    "system": "up down restart sleep wake status logs",
}
_GLOBAL_OPTS = "--json --jq --yes -y --api-url --token --help -h"

_BASH_TEMPLATE = """\
# joidy bash completion — generated by `joidy completion bash`
# Install: joidy completion bash > ~/.local/share/bash-completion/completions/joidy
_joidy() {
    local cur prev
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    local groups="%GROUPS%"
    local top="%TOP%"
    local opts="%OPTS%"

    case "$prev" in
        --jq|--api-url|--token) return 0 ;;
    esac
    case "$cur" in
        -*) COMPREPLY=( $(compgen -W "$opts" -- "$cur") ); return 0 ;;
    esac

    local group=""
    for g in $groups; do
        for ((i=1; i<COMP_CWORD; i++)); do
            [ "${COMP_WORDS[i]}" = "$g" ] && group="$g"
        done
    done
    if [ -n "$group" ]; then
        case "$group" in
%SUBCASES%
        esac
    fi
    COMPREPLY=( $(compgen -W "$top" -- "$cur") )
}
complete -F _joidy joidy
"""

_ZSH_TEMPLATE = """\
#compdef joidy
# joidy zsh completion — generated by `joidy completion zsh`
# Install: joidy completion zsh > "${fpath[1]}/_joidy"
_joidy() {
    local -a top opts
    top=(%TOP%)
    opts=(%OPTS%)
    if (( CURRENT == 2 )); then
        _describe 'command' top
        return
    fi
    case "$words[2]" in
%SUBCASES%
        *) _arguments '*: :_files' ;;
    esac
}
_joidy "$@"
"""


def _bash_subcases() -> str:
    lines = []
    for group, subs in _SUBCOMMANDS.items():
        lines.append(f'            {group}) COMPREPLY=( $(compgen -W "{subs}" -- "$cur") ); return 0 ;;')
    return "\n".join(lines)


def _zsh_subcases() -> str:
    lines = []
    for group, subs in _SUBCOMMANDS.items():
        words = " ".join(f"'{s}'" for s in subs.split())
        lines.append(f"        {group}) _describe '{group} command' '({words})' ;;")
    return "\n".join(lines)


_FISH_TEMPLATE = """\
# joidy fish completion — generated by `joidy completion fish`
# Install: joidy completion fish > ~/.config/fish/completions/joidy.fish
complete -c joidy -f
%TOP_LINES%
%SUB_LINES%
complete -c joidy -s h -l help -d 'Show help'
complete -c joidy -l json -d 'Emit raw JSON output'
complete -c joidy -l jq -r -d 'JMESPath output filter'
complete -c joidy -s y -l yes -d 'Skip confirmation prompts'
complete -c joidy -l api-url -r -d 'Joidy API base URL'
complete -c joidy -l token -r -d 'Bearer token'
"""


def _fish_script() -> str:
    top_lines = "\n".join(f"complete -c joidy -n '__fish_use_subcommand' -a '{cmd}'" for cmd in _TOP_LEVEL.split())
    sub_lines = "\n".join(
        f"complete -c joidy -n '__fish_seen_subcommand_from {group}' -a '{subs}'"
        for group, subs in _SUBCOMMANDS.items()
    )
    return _FISH_TEMPLATE.replace("%TOP_LINES%", top_lines).replace("%SUB_LINES%", sub_lines)


_SHELLS = ("bash", "zsh", "fish")


def completion_script(shell: str) -> str:
    if shell == "bash":
        return (
            _BASH_TEMPLATE.replace("%GROUPS%", " ".join(_SUBCOMMANDS))
            .replace("%TOP%", _TOP_LEVEL)
            .replace("%OPTS%", _GLOBAL_OPTS)
            .replace("%SUBCASES%", _bash_subcases())
        )
    if shell == "zsh":
        return (
            _ZSH_TEMPLATE.replace("%TOP%", " ".join(f"'{c}'" for c in _TOP_LEVEL.split()))
            .replace("%OPTS%", " ".join(f"'{o}'" for o in _GLOBAL_OPTS.split()))
            .replace("%SUBCASES%", _zsh_subcases())
        )
    return _fish_script()


def completion(
    ctx: typer.Context,
    shell: Annotated[str, typer.Argument(help="Target shell: bash, zsh or fish.")],
    json: JSONOpt = False,
    jq: JQOpt = None,
    yes: YesOpt = False,
    api_url: ApiUrlOpt = None,
    token: TokenOpt = None,
) -> None:
    """Print the shell completion script.

    Install example: ``joidy completion bash > ~/.local/share/bash-completion/completions/joidy``
    """
    _ = Flags.make(ctx, json=json, jq=jq, yes=yes, api_url=api_url, token=token)
    shell = shell.lower()
    if shell not in _SHELLS:
        output.die(f"unsupported shell '{shell}' (allowed: {', '.join(_SHELLS)})", output.EXIT_USAGE)
    typer.echo(completion_script(shell))
