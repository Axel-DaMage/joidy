from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://joidy:joidy@postgres:5432/joidy"
    ai_service_url: str = "http://ai-service:8002"
    worker_url: str = "http://worker:8001"
    secret_key: str = "dev_secret_change_me"
    app_env: str = "development"
    cors_allowed_origins: str = ""  # Comma-separated origins for production (e.g. "https://joidy.app,https://www.joidy.app")

    # GitHub Integration (OAuth - Device Flow)
    github_client_id: str = ""
    github_client_secret: str = ""
    github_oauth_web_url: str = ""
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

    # Authentication
    auth_password: str = ""  # Password for single-user auth (optional)


settings = Settings()
