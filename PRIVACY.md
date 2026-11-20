# Privacy Policy

**Last updated:** 2026-11-20

Joidy is a self-hosted, local-first personal knowledge management application.
This policy describes what data the software accesses, where it is stored, how
it is used, and when (if ever) it leaves your machine.

## Summary

- **Local-first.** All application data is stored on infrastructure you control:
  a PostgreSQL database inside your own Docker deployment and your Obsidian
  vault on your own filesystem.
- **Zero telemetry.** Joidy collects no analytics, no crash reports, and no
  usage statistics. Nothing is sent to the project maintainer or to any
  Joidy-operated server — there is no Joidy-operated server.
- **No sale, no ads.** Your data is never sold, rented, or used for
  advertising.
- **Third parties only on your request.** External services (Google, Gemini,
  GitHub, Telegram, Spotify, Strava, AI providers) are contacted **only** when
  you explicitly configure the corresponding credentials. With no credentials
  configured, Joidy makes no third-party API calls at all.
- **You are the data controller.** Because you host the software, you decide
  where data lives, who can access it, and when it is deleted.

## 1. Data the application stores

Joidy stores the following user data, all of it inside your own deployment:

| Data | Where it is stored |
|------|--------------------|
| Notes, tags, links, embeddings | `notes`, `tags`, `note_tags`, `note_links`, `note_embeddings`, `tag_cooccurrences`, `embedding_failures` tables in the `postgres` container (Docker volume `postgres_data`); note content is also mirrored as `.md` files in your Obsidian vault (`OBSIDIAN_VAULT_PATH`) |
| Goals, streaks, mood, gamification state | `goals`, `personal_streaks`, `streak_checkins`, `mood_entries`, `xp_events`, `streak_records`, `user_stats`, `achievements` tables |
| Google OAuth tokens | `google_tokens` table — the refresh token is encrypted at rest with Fernet, keyed by your `SECRET_KEY` |
| Google Calendar data (cached copy) | `google_calendar_events`, `google_calendar_sync_state`, `calendar_tasks` tables |
| Gmail messages (imported via your own n8n workflow) | `email_messages` table (subject, sender, snippet, body text, labels) |
| GitHub synced items | `github_repos`, `github_items`, `github_events` tables |
| Telegram bot activity | `telegram_events` table (command, sender, status, response) |
| AI chat history | `chat_sessions` table |
| App settings, API keys, OAuth client secrets | the `.env` file on your host filesystem (git clone: `./.env`; system install: `~/.config/joidy/.env`) and the `system_config` table |
| Session token, UI preferences | your browser's `localStorage` |
| Database backups | `pg_dump` files under `JOIDY_DATA_DIR/backups` (`./data/backups` or `~/.local/share/joidy/data/backups`) |

## 2. Third-party services and OAuth scopes

Each integration is **disabled until you configure it**. When enabled, Joidy
requests only the scopes listed below.

### Google (Calendar, Tasks, Gmail, Contacts)

Configured via `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`. Joidy requests:

| Scope | Purpose |
|-------|---------|
| `https://www.googleapis.com/auth/calendar.events` | Create, update and delete events on your calendars (write-back from Joidy tasks) |
| `https://www.googleapis.com/auth/calendar.readonly` | Read your calendar list and events |
| `https://www.googleapis.com/auth/tasks.readonly` | Read your Google Tasks lists |
| `https://www.googleapis.com/auth/gmail.readonly` | Read your Gmail message metadata and content |
| `https://www.googleapis.com/auth/contacts.readonly` | Read your Google Contacts |

**Google API Services User Data Policy — Limited Use disclosure:** data
obtained through Google APIs is used exclusively to provide the user-facing
features you invoked (viewing calendars/tasks/emails/contacts inside Joidy and
writing back calendar events you create). It is **not** used to develop,
improve, or train generalized AI/ML models; **not** transferred to third
parties except as required to provide the feature; **not** used for
advertising; and **not** read by humans. All Google-derived data stays in your
own database or vault.

### GitHub

Configured via `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` (OAuth) or
`GITHUB_TOKEN` (personal access token). OAuth scopes requested: `repo`,
`read:user`, `user:email`, `workflow`. Used to read your repositories, issues
and pull requests and to receive repository webhooks you configure.

### AI providers

Configured via `GEMINI_API_KEY` or one of the optional providers (`OPENAI`,
`ANTHROPIC`, `COHERE`, `OLLAMA`, `OPENROUTER`). When you use embeddings,
classification, semantic search or chat, the relevant note content is sent to
the provider you configured. With Ollama, processing stays on your own host.
With no AI key configured, this data never leaves your deployment.

### Telegram

Configured via `TELEGRAM_BOT_TOKEN`. When enabled, the bot registers an
authenticated webhook (`POST /telegram/webhook`, verified with
`TELEGRAM_WEBHOOK_SECRET`) and replies only to your
`TELEGRAM_ALLOWED_USER_ID`. Message content sent to your bot is processed by
Telegram under Telegram's own privacy policy.

### Spotify and Strava (scaffolded integrations)

Configured via `SPOTIFY_CLIENT_ID/SECRET` and `STRAVA_CLIENT_ID/SECRET`.
Scopes: Spotify `user-read-recently-played`, `user-read-playback-state`,
`user-top-read`, `playlist-read-private`; Strava `read`, `activity:read`.
Read-only access to your listening/activity data when you connect them.

### n8n (optional, self-hosted)

If you run the included n8n workflows, your own n8n instance pushes Gmail
messages into Joidy's `/emails` API. n8n runs under your control; no data is
shared with n8n's vendor unless you configure it to.

## 3. Data sharing

Joidy itself does not transmit your data to anyone. The only outbound flows
are the third-party API calls listed above, each of which:

- is initiated only after you configure credentials, and
- sends only the data required for the feature you invoked.

Each third-party processor handles that data under its own privacy policy
(Google, GitHub, Telegram, Spotify, Strava, your chosen AI provider).

## 4. Retention and deletion

- **Retention:** data is kept until you delete it. Local backups follow the
  configured retention (`BACKUP_RETENTION_DAYS`, default 14 days, plus
  `BACKUP_RETENTION_WEEKS`, default 4 weekly snapshots).
- **Disconnect an integration:** `POST /integrations/google/disconnect`
  deletes the stored Google OAuth tokens. Revoking access in your Google,
  GitHub, Spotify or Strava account stops all further access.
- **Delete content:** notes, goals, streaks and emails can be deleted from
  the UI or by deleting the corresponding `.md` file in your vault.
- **Delete everything:** stopping the stack and removing the `postgres_data`
  volume, the `data/` directory and your `.env` file removes all
  application-stored data (`docker compose down -v` / `make dev-reset` in
  development). Vault files remain regular files you can delete normally.
- **Export:** `GET /export/notes/markdown` and `GET /export/notes/html`
  provide your notes for portability before deletion.

## 5. Your responsibilities as a self-hoster

Because you operate the service, **you are the data controller** for any
personal data it processes — including data belonging to other people that
appears in your synced Gmail, Contacts or Calendar. Depending on your
jurisdiction (e.g. GDPR), you may have obligations regarding that data. The
Joidy project, as an open-source software provider, does not access, collect
or process your data.

Keep your `SECRET_KEY`, `.env` and host filesystem private: they protect your
encrypted OAuth tokens and API credentials.

## 6. Security

- OAuth refresh tokens are stored Fernet-encrypted (`SECRET_KEY`-derived key).
- API endpoints require JWT authentication except auth/config/webhook routes.
- Published ports bind to `127.0.0.1` by default; exposing Joidy to a LAN or
  the internet is your choice and responsibility.
- Report vulnerabilities privately per [SECURITY.md](SECURITY.md).

## 7. Changes to this policy

Changes are tracked in git history. Material changes are announced in
release notes.

## 8. Contact

- General questions: open a discussion or issue at
  <https://github.com/Axel-DaMage/joidy/issues>
- Privacy/security reports: **<d4mag3@duck.com>**
