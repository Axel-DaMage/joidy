"""Stack-management delegation.

The data-plane CLI does not reimplement Docker orchestration — ``joidy
up/down/status/logs/...`` forwards to the existing ``scripts/joidy.sh``
stack CLI, resolved the same way that script resolves its project dir:

1. ``$JOIDY_STACK_CLI`` — explicit path to a stack script/binary
2. ``$JOIDY_DIR/scripts/joidy.sh``
3. ``~/.config/joidy/path`` → ``<dir>/scripts/joidy.sh``
4. ``/etc/joidy/path`` → ``<dir>/scripts/joidy.sh`` (system/AUR install)
5. ``/usr/share/joidy/scripts/joidy.sh`` (AUR layout)
6. A ``joidy`` shell script on PATH (the bash CLI coexisting with this one)

``joidy status --json`` (or piped status) bypasses the delegate and emits
``docker compose ps --format json`` as a JSON array for agents.
"""

from __future__ import annotations

import json as _json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import output

STACK_COMMANDS = ("up", "down", "restart", "sleep", "wake", "status", "logs", "backup", "restore", "idle", "pull")


def _project_dir_candidates() -> list[Path]:
    candidates: list[Path] = []
    joidy_dir = os.environ.get("JOIDY_DIR")
    if joidy_dir:
        candidates.append(Path(joidy_dir))
    for pointer in (Path.home() / ".config" / "joidy" / "path", Path("/etc/joidy/path")):
        try:
            if pointer.is_file():
                candidates.append(Path(pointer.read_text(encoding="utf-8").strip()))
        except OSError:
            continue
    return candidates


def project_dir() -> Path | None:
    for candidate in _project_dir_candidates():
        if (candidate / "docker-compose.yml").is_file():
            return candidate
    return None


def find_stack_cli() -> Path | None:
    """Locate the bash stack CLI without mistaking this Python entry point for it."""
    explicit = os.environ.get("JOIDY_STACK_CLI")
    if explicit:
        return Path(explicit) if Path(explicit).exists() else None

    for candidate in _project_dir_candidates():
        script = candidate / "scripts" / "joidy.sh"
        if script.is_file():
            return script

    aur = Path("/usr/share/joidy/scripts/joidy.sh")
    if aur.is_file():
        return aur

    for name in ("joidy", "joidy.sh"):
        found = shutil.which(name)
        if found and _looks_like_shell_script(Path(found)):
            return Path(found)
    return None


def _looks_like_shell_script(path: Path) -> bool:
    try:
        with path.open("rb") as fh:
            shebang = fh.readline(200)
    except OSError:
        return False
    return b"/sh" in shebang or b"/bash" in shebang or b"/zsh" in shebang


def run(argv: list[str]) -> int:
    """Forward ``argv`` to the stack CLI; returns its exit code."""
    script = find_stack_cli()
    if script is None:
        output.die(
            "stack CLI not found — set JOIDY_STACK_CLI or JOIDY_DIR, or create ~/.config/joidy/path",
            output.EXIT_USAGE,
        )
    try:
        proc = subprocess.run([str(script), *argv], check=False)
    except OSError as exc:
        output.die(f"failed to run stack CLI {script}: {exc}", output.EXIT_ERROR)
        return output.EXIT_ERROR  # unreachable
    return proc.returncode


def status_json() -> None:
    """Emit ``docker compose ps`` as a JSON array (agent-facing ``joidy status --json``)."""
    proj = project_dir()
    if proj is None:
        output.die(
            "Joidy project dir not found — set JOIDY_DIR or create ~/.config/joidy/path",
            output.EXIT_USAGE,
        )
    try:
        proc = subprocess.run(
            ["docker", "compose", "ps", "--format", "json"],
            cwd=proj,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        output.die("docker is not installed or not on PATH", output.EXIT_SERVER)
        return  # unreachable
    if proc.returncode != 0:
        output.die(f"docker compose ps failed: {proc.stderr.strip()}", output.EXIT_SERVER)
    # `compose ps --format json` emits one JSON object per line.
    services = [_json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
    output.emit(services, json_mode=True)


def status_tty() -> int:
    """Interactive ``joidy status`` — human output via the stack CLI."""
    return run(["status"])


def status(*, json_mode: bool) -> int | None:
    if json_mode or not sys.stdout.isatty():
        status_json()
        return None
    return status_tty()
