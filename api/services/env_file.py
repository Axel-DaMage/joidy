"""Read/write access to the deployment's ``.env`` file.

Lives in ``services/`` because both ``routers/config.py`` (settings UI) and
``services/auth_service.py`` (cross-worker password lookup) need it, and a
router must never be imported from a service.
"""

import os
from pathlib import Path


def _default_env_file() -> Path:
    """The deployment's ``.env`` when ``JOIDY_ENV_FILE`` is not set.

    ``/app/.env`` inside Docker (the compose bind-mount target), the repo-root
    ``.env`` otherwise.
    """
    if Path("/app").exists():
        return Path("/app/.env")
    return Path(__file__).parent.parent.parent / ".env"


def get_env_file() -> Path:
    """Resolve the env file path, honoring the ``JOIDY_ENV_FILE`` override.

    ``JOIDY_ENV_FILE`` already selects the host-side bind-mount source in
    docker-compose; honoring it in Python as well lets read-only installs and
    the test suite (#991) redirect persistence without touching the real
    ``.env``. Resolved on every call (not at import) so tests can point it at a
    per-test file after app modules are already imported.
    """
    return Path(os.getenv("JOIDY_ENV_FILE") or _default_env_file())


# Kept as a module-level constant for backwards compatibility (re-exported by
# ``routers/config.py``). Prefer ``get_env_file()`` — it picks up runtime
# changes to ``JOIDY_ENV_FILE``.
ENV_FILE = get_env_file()


def read_env() -> dict:
    """Parse the env file into a dict, ignoring comments and blank lines.

    Uses ``is_file`` instead of ``exists``: when the bind mount source does not
    exist on the host, Docker silently creates /app/.env as a *directory* and
    ``open()`` raised IsADirectoryError, turning every /config request into a
    500 and breaking the whole settings page.
    """
    env_vars: dict[str, str] = {}
    env_file = get_env_file()
    if env_file.is_file():
        with open(env_file) as f:
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
    env_file = get_env_file()
    lines: list[str] = []
    if env_file.is_file():
        with open(env_file) as f:
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

    with open(env_file, "w") as f:
        f.write("\n".join(output).rstrip("\n") + "\n")


def get_persisted(key: str) -> str:
    """Read a single key straight from disk.

    Needed because uvicorn runs with ``--workers``: a value written by the
    worker that handled a request is invisible to its siblings, whose in-memory
    ``settings`` object still holds the value loaded at startup.
    """
    return read_env().get(key, "")
