"""Client-side configuration for the Joidy CLI.

Config lives at ``$JOIDY_CONFIG_DIR/config.toml`` — by default
``~/.config/joidy/config.toml`` — and is written with mode 0600.

Environment variables always win over the file:

- ``JOIDY_API_URL`` overrides ``[api].url``
- ``JOIDY_TOKEN`` overrides ``[auth].token``

This lets agents target a local dev stack, the Docker install, or a remote
instance without touching the user's stored credentials.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

DEFAULT_API_URL = "http://localhost:8000"


def config_dir() -> Path:
    """Directory holding ``config.toml`` (``$JOIDY_CONFIG_DIR`` override)."""
    override = os.environ.get("JOIDY_CONFIG_DIR")
    if override:
        return Path(override)
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "joidy"


def config_path() -> Path:
    return config_dir() / "config.toml"


def load() -> dict[str, Any]:
    path = config_path()
    if not path.is_file():
        return {}
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def save(cfg: dict[str, Any]) -> Path:
    directory = config_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = config_path()
    path.write_text(_dump_toml(cfg), encoding="utf-8")
    path.chmod(0o600)
    return path


def _toml_str(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _dump_toml(cfg: dict[str, Any]) -> str:
    lines: list[str] = []
    for section, values in sorted(cfg.items()):
        lines.append(f"[{section}]")
        for key, value in sorted(values.items()):
            if isinstance(value, bool):
                rendered = "true" if value else "false"
            elif isinstance(value, (int, float)):
                rendered = str(value)
            else:
                rendered = _toml_str(str(value))
            lines.append(f"{key} = {rendered}")
        lines.append("")
    return "\n".join(lines)


def get_api_url(cli_value: str | None = None) -> str:
    """Effective API base URL: flag > ``JOIDY_API_URL`` > config > default."""
    if cli_value:
        return cli_value
    env = os.environ.get("JOIDY_API_URL")
    if env:
        return env
    stored = (load().get("api") or {}).get("url")
    return stored or DEFAULT_API_URL


def get_token(cli_value: str | None = None) -> tuple[str | None, str]:
    """Effective bearer token and its source: flag > ``JOIDY_TOKEN`` > config."""
    if cli_value:
        return cli_value, "flag"
    env = os.environ.get("JOIDY_TOKEN")
    if env:
        return env, "env"
    stored = (load().get("auth") or {}).get("token")
    if stored:
        return stored, "config"
    return None, "none"


def store_token(token: str, api_url: str | None = None) -> Path:
    cfg = load()
    cfg.setdefault("auth", {})["token"] = token
    if api_url:
        cfg.setdefault("api", {})["url"] = api_url
    return save(cfg)


def store_api_url(api_url: str) -> Path:
    cfg = load()
    cfg.setdefault("api", {})["url"] = api_url
    return save(cfg)


def clear_token() -> Path:
    cfg = load()
    cfg.setdefault("auth", {}).pop("token", None)
    return save(cfg)
