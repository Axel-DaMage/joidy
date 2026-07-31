from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://joidy:joidy@postgres:5432/joidy"
    ai_service_url: str = "http://ai-service:8002"
    worker_url: str = "http://worker:8001"
    secret_key: str = ""
    app_env: str = "development"
    cors_allowed_origins: str = ""  # Comma-separated origins for production (e.g. "https://joidy.app,https://www.joidy.app")

    # GitHub Integration (OAuth - Web Flow + Device Flow)
    github_client_id: str = ""
    github_client_secret: str = ""
    github_oauth_web_url: str = ""  # Redirect URL for Web Flow callback
    github_token: str = ""
    github_username: str = ""
    github_webhook_url: str = ""

    # AI & Embeddings
    embedding_retry_max_attempts: int = 8
    embedding_retry_base_seconds: int = 60
    xp_table_json: str = ""

    # File uploads
    upload_dir: str = "data/uploads"
    upload_max_image_bytes: int = 10 * 1024 * 1024  # 10 MB
    upload_max_file_bytes: int = 50 * 1024 * 1024   # 50 MB

    # Logging
    log_dir: str = "data/logs"

    # Web Push (VAPID) for real push notifications
    vapid_private_key: str = ""
    vapid_public_key: str = ""
    vapid_claim_email: str = "contacto@joidy.dev"

    # Authentication
    auth_password: str = ""  # Password for single-user auth (optional)

    # Obsidian
    obsidian_webhook_secret: str | None = None  # Optional secret for /webhook/obsidian
    obsidian_vault_path: str = "/vault"  # Container-internal mount path of the Obsidian vault

    # Google OAuth (Calendar, Tasks, Gmail, Contacts)
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = ""

    # Strava OAuth (Activities, Athlete data)
    strava_client_id: str = ""
    strava_client_secret: str = ""
    strava_redirect_uri: str = ""

    # Spotify OAuth (Playback, Playlists, Top tracks)
    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    spotify_redirect_uri: str = ""


settings = Settings()
