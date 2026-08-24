"""Read/write access to the deployment's ``.env`` file.

Lives in ``services/`` because both ``routers/config.py`` (settings UI) and
``services/auth_service.py`` (cross-worker password lookup) need it, and a
router must never be imported from a service.
"""

from pathlib import Path

ENV_FILE = Path("/app/.env") if Path("/app").exists() else Path(__file__).parent.parent.parent / ".env"


def read_env() -> dict:
    """Parse the env file into a dict, ignoring comments and blank lines.

    Uses ``is_file`` instead of ``exists``: when the bind mount source does not
    exist on the host, Docker silently creates /app/.env as a *directory* and
    ``open()`` raised IsADirectoryError, turning every /config request into a
    500 and breaking the whole settings page.
    """
    env_vars: dict[str, str] = {}
    if ENV_FILE.is_file():
        with open(ENV_FILE) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()
    return env_vars


def write_env(env_vars: dict) -> None:
    """Persist ``env_vars`` while keeping the file's comments and layout.

    The previous implementation rewrote the file from scratch as a flat list of
    ``KEY=VALUE`` lines, which destroyed every comment and commented-out
    template entry the user (or ``.env.example``) had — including the hints
    needed to configure the app later.
    """
    lines: list[str] = []
    if ENV_FILE.is_file():
        with open(ENV_FILE) as f:
            lines = f.read().splitlines()

    remaining = dict(env_vars)
    output: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in remaining:
                output.append(f"{key}={remaining.pop(key)}")
                continue
        output.append(line)

    if remaining:
        if output and output[-1].strip():
            output.append("")
        output.extend(f"{key}={value}" for key, value in remaining.items())

    with open(ENV_FILE, "w") as f:
        f.write("\n".join(output).rstrip("\n") + "\n")


def get_persisted(key: str) -> str:
    """Read a single key straight from disk.

    Needed because uvicorn runs with ``--workers``: a value written by the
    worker that handled a request is invisible to its siblings, whose in-memory
    ``settings`` object still holds the value loaded at startup.
    """
    return read_env().get(key, "")
