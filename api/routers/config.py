from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/config", tags=["config"])

ENV_FILE = Path(__file__).parent.parent.parent / ".env"

CONFIG_KEYS = {
    "gemini_api_key": "GEMINI_API_KEY",
    "obsidian_vault_path": "OBSIDIAN_VAULT_PATH",
    "daily_notes_folder": "DAILY_NOTES_FOLDER",
    "github_token": "GITHUB_TOKEN",
    "github_username": "GITHUB_USERNAME",
    "github_client_id": "GITHUB_CLIENT_ID",
    "github_client_secret": "GITHUB_CLIENT_SECRET",
    "telegram_bot_token": "TELEGRAM_BOT_TOKEN",
    "telegram_allowed_user_id": "TELEGRAM_ALLOWED_USER_ID",
    "secret_key": "SECRET_KEY",
    "app_env": "APP_ENV",
}

PUBLIC_KEYS = {
    "gemini_api_key": False,
    "obsidian_vault_path": True,
    "daily_notes_folder": True,
    "github_token": False,
    "github_username": True,
    "github_client_id": False,
    "github_client_secret": False,
    "telegram_bot_token": False,
    "telegram_allowed_user_id": False,
    "secret_key": False,
    "app_env": True,
}


def read_env() -> dict:
    env_vars = {}
    if ENV_FILE.exists():
        with open(ENV_FILE) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()
    return env_vars


def write_env(env_vars: dict) -> None:
    with open(ENV_FILE, "w") as f:
        f.write("# Joidy Configuration\n")
        f.write("# Edit this file or use the web interface\n\n")
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")


class ConfigResponse(BaseModel):
    gemini_api_key: str | None = None
    obsidian_vault_path: str | None = None
    daily_notes_folder: str | None = None
    github_username: str | None = None
    app_env: str | None = None
    configured_keys: list[str]


class ConfigUpdate(BaseModel):
    gemini_api_key: str | None = None
    obsidian_vault_path: str | None = None
    daily_notes_folder: str | None = None
    github_token: str | None = None
    github_username: str | None = None
    github_client_id: str | None = None
    github_client_secret: str | None = None
    telegram_bot_token: str | None = None
    telegram_allowed_user_id: str | None = None
    secret_key: str | None = None


@router.get("", response_model=ConfigResponse)
def get_config():
    env_vars = read_env()
    configured = []
    response_data = {}

    for short_key, env_key in CONFIG_KEYS.items():
        value = env_vars.get(env_key, "")
        is_public = PUBLIC_KEYS.get(short_key, False)

        if value and value not in ("", "your_gemini_api_key_here", "change_this_to_a_random_secret_key"):
            configured.append(short_key)

        if is_public:
            response_data[short_key] = value if value else None
        else:
            response_data[short_key] = None

    return ConfigResponse(
        **response_data,
        configured_keys=configured
    )


@router.post("")
def update_config(update: ConfigUpdate):
    env_vars = read_env()

    update_data = update.model_dump(exclude_none=True)

    for short_key, env_key in CONFIG_KEYS.items():
        if short_key in update_data:
            value = update_data[short_key]
            if value is not None:
                env_vars[env_key] = value

    write_env(env_vars)

    return {"status": "ok", "message": "Configuration updated. Some changes may require a restart."}


@router.get("/keys")
def get_available_keys():
    return {
        "keys": [
            {
                "key": short_key,
                "env_key": env_key,
                "public": PUBLIC_KEYS.get(short_key, False),
                "description": get_key_description(short_key),
            }
            for short_key, env_key in CONFIG_KEYS.items()
        ]
    }


def get_key_description(key: str) -> str:
    descriptions = {
        "gemini_api_key": "API key for Google Gemini AI",
        "obsidian_vault_path": "Absolute path to your Obsidian vault",
        "daily_notes_folder": "Relative folder inside your vault for daily notes",
        "github_token": "GitHub Personal Access Token",
        "github_username": "GitHub username",
        "github_client_id": "GitHub OAuth App client ID",
        "github_client_secret": "GitHub OAuth App client secret",
        "telegram_bot_token": "Telegram Bot API token",
        "telegram_allowed_user_id": "Your Telegram user ID",
        "secret_key": "Session signing secret key",
        "app_env": "Application environment (development/production)",
    }
    return descriptions.get(key, "")


class GamificationConfig(BaseModel):
    xp_table: dict
    plant_stages: list[dict]
    streak_milestones: list[int]


@router.get("/gamification", response_model=GamificationConfig)
def get_gamification_config():
    from api.services.gamification_engine import (
        PLANT_STAGES,
        STREAK_MILESTONES,
        get_xp_table,
    )
    xp_table = get_xp_table()
    return GamificationConfig(
        xp_table=xp_table,
        plant_stages=[
            {"stage": i, "name": stage["name"], "xp_required": stage["xp_required"]}
            for i, stage in enumerate(PLANT_STAGES)
        ],
        streak_milestones=STREAK_MILESTONES
    )
