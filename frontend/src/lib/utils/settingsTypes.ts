// Shared types for the SettingsPanel section components (#210).

export interface SystemConfig {
  gemini_api_key: string;
  obsidian_vault_path: string;
  daily_notes_folder: string;
  github_token: string;
  github_username: string;
  github_client_id: string;
  github_client_secret: string;
  google_client_id: string;
  google_client_secret: string;
  google_redirect_uri: string;
  openai_api_key: string;
  openai_base_url: string;
  llm_model: string;
  embedding_model: string;
  telegram_bot_token: string;
  telegram_allowed_user_id: string;
}
