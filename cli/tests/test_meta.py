"""Meta surface: --version, --help, bare invocation, commands, completion, exit codes."""

import json

import httpx
from joidy_cli import __version__

from tests.conftest import combined, output_json


def test_version(invoke):
    result = invoke("--version")
    assert result.exit_code == 0
    assert __version__ in result.output


def test_help(invoke):
    result = invoke("--help")
    assert result.exit_code == 0
    for name in ("auth", "notes", "goals", "streaks", "system", "commands", "completion"):
        assert name in result.output


def test_bare_invocation_non_tty_prints_help(invoke):
    # Not a TTY → help text, exit 0 (never blocks).
    result = invoke()
    assert result.exit_code == 0
    assert "COMMAND" in result.output.upper() or "Commands" in result.output


def test_commands_json(invoke):
    result = invoke("commands", "--json")
    assert result.exit_code == 0
    data = output_json(result)
    paths = [c["path"] for c in data["commands"]]
    for expected in (
        "auth login",
        "notes new",
        "goals done <id>",
        "streaks checkin <id>",
        "completion <shell>",
    ):
        assert expected in paths
    assert data["exit_codes"]["4"]


def test_commands_jq(invoke):
    result = invoke("commands", "--jq", "commands[].path")
    assert result.exit_code == 0
    paths = output_json(result)
    assert "notes new" in paths


def test_completion_all_shells(invoke):
    for shell in ("bash", "zsh", "fish"):
        result = invoke("completion", shell)
        assert result.exit_code == 0, shell
        assert "joidy" in result.output


def test_completion_invalid_shell(invoke):
    result = invoke("completion", "tcsh")
    assert result.exit_code == 2
    assert "unsupported shell" in combined(result)


def test_error_exit_codes(invoke, api):
    api.respond["fn"] = lambda req: httpx.Response(404, json={"detail": "Note not found"})
    result = invoke("notes", "get", "999")
    assert result.exit_code == 4

    api.respond["fn"] = lambda req: httpx.Response(401, json={"detail": "Not authenticated"})
    result = invoke("notes", "ls")
    assert result.exit_code == 3
    assert "auth login" in combined(result)

    api.respond["fn"] = lambda req: httpx.Response(500, json={"detail": "boom"})
    result = invoke("notes", "ls")
    assert result.exit_code == 5

    def unreachable(req):
        raise httpx.ConnectError("refused", request=req)

    api.respond["fn"] = unreachable
    result = invoke("notes", "ls")
    assert result.exit_code == 5


def test_invalid_jq_is_usage_error(invoke, api):
    api.respond["fn"] = lambda req: httpx.Response(200, json=[])
    result = invoke("notes", "ls", "--jq", "[[[")
    assert result.exit_code == 2


def test_non_tty_output_is_json_by_default(invoke, api):
    api.respond["fn"] = lambda req: httpx.Response(200, json=[{"id": 1, "title": "x"}])
    result = invoke("notes", "ls")
    assert result.exit_code == 0
    assert json.loads(result.output) == [{"id": 1, "title": "x"}]
