import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # JOIDY_ENV_FILE mirrors services.env_file.get_env_file() (#991): the test
    # suite points it at an isolated empty file so a developer's populated .env
    # cannot leak into Settings at import time.
    model_config = SettingsConfigDict(env_file=os.getenv("JOIDY_ENV_FILE") or ".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://joidy:joidy@postgres:5432/joidy"
    ai_service_url: str = "http://ai-service:8002"
    ai_service_enabled: bool = True  # Set to false in production to skip AI calls
    worker_url: str = "http://worker:8001"
    secret_key: str = ""
    internal_secret: str = ""  # Shared secret for API → ai-service auth
    internal_api_token: str = ""  # Dedicated service token for worker/n8n → API auth (#1275)
    app_env: str = "development"
    cors_allowed_origins: str = (
        ""  # Comma-separated origins for production (e.g. "https://joidy.app,https://www.joidy.app")
    )
    # Comma-separated IPs/CIDRs of trusted reverse proxies. X-Forwarded-For is
    # only honored (for rate-limit bucketing) when the direct peer matches one
    # of these (#1276). Empty = always use the direct peer IP.
    trusted_proxies: str = ""
    # Power management (Settings → Servicios) — opt-in (#1278). When false the
    # /system/power mutation routes are not registered at all and
    # /system/power/status reports docker_available=false. The engine socket
    # is only mounted via the docker-compose.power.yml overlay, never by the
    # base docker-compose.yml.
    power_management_enabled: bool = False

    # GitHub Integration (OAuth - Web Flow + Device Flow)
    github_client_id: str = ""
    github_client_secret: str = ""
    github_oauth_web_url: str = ""  # Redirect URL for Web Flow callback
    github_token: str = ""
    github_username: str = ""
    github_webhook_url: str = ""
    # Shared secret GitHub signs webhook deliveries with (X-Hub-Signature-256).
    # Per-repo secrets generated during webhook setup take precedence; when
    # neither is configured the webhook endpoint fails closed (#1318).
    github_webhook_secret: str = ""

    # AI & Embeddings
    embedding_retry_max_attempts: int = 8
    embedding_retry_base_seconds: int = 60
    xp_table_json: str = ""

    # File uploads
    upload_dir: str = "data/uploads"
    upload_max_image_bytes: int = 10 * 1024 * 1024  # 10 MB
    upload_max_file_bytes: int = 50 * 1024 * 1024  # 50 MB

    # Logging
    log_dir: str = "data/logs"

    # Web Push (VAPID) for real push notifications
    vapid_private_key: str = ""
    vapid_public_key: str = ""
    vapid_claim_email: str = "contacto@joidy.dev"

    # Authentication
    auth_password: str = ""  # Password for single-user auth (optional)
    # JWT lifecycle (#1285): short-lived access tokens are renewed silently
    # via POST /auth/refresh with a longer-lived rotating refresh token.
    access_token_expire_minutes: int = 720  # 12h — within the 12–24h audit bound
    refresh_token_expire_days: int = 7
    # bcrypt cost factor for password hashing. None = library default (12).
    # Tests set BCRYPT_ROUNDS=4 via conftest — hash strength is irrelevant
    # there and bcrypt was the slowest single test in the suite (#996).
    bcrypt_rounds: int | None = None

    # Obsidian
    obsidian_webhook_secret: str | None = None  # Optional secret for /webhook/obsidian
    obsidian_vault_path: str = "/vault"  # Container-internal mount path of the Obsidian vault

    # Google OAuth (Calendar, Tasks, Gmail, Contacts)
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = ""
    # Gmail push notifications (#42): Pub/Sub topic users.watch publishes to
    # (projects/<project>/topics/<topic>). Empty = POST /integrations/gmail/watch
    # reports 503; polling via GET /messages?since= and GET /history still works.
    google_gmail_pubsub_topic: str = ""

    # Strava OAuth (Activities, Athlete data)
    strava_client_id: str = ""
    strava_client_secret: str = ""
    strava_redirect_uri: str = ""
    # Verify token for the Strava webhook subscription handshake (#44).
    # Empty = /integrations/strava/webhook disabled (404).
    strava_webhook_verify_token: str = ""

    # Spotify OAuth (Playback, Playlists, Top tracks)
    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    spotify_redirect_uri: str = ""

    # Telegram Bot (quick capture via /telegram/webhook)
    telegram_bot_token: str = ""
    telegram_allowed_user_id: str = ""  # When set, only this Telegram user ID can use the bot
    telegram_webhook_secret: str = ""  # Optional secret_token verified on incoming webhooks

    # User timezone for day-boundary calculations (streaks, gamification, mood).
    # IANA zone name (e.g. "America/Santiago", "Europe/Madrid"). Defaults to UTC
    # so behaviour is unchanged when not configured. See issue #650.
    user_timezone: str = "UTC"


settings = Settings()
