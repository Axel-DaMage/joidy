# Joidy API Reference

## Metadata

```yaml
version: 1.0.0-beta.1
base_url: http://localhost:8000
docs_url: http://localhost:8000/docs
framework: FastAPI
language: Python 3.12
```

---

## 1. Authentication

**JWT auth required on all endpoints except `/health`, `/auth/login`, and `/config/setup-status`.**

The API enforces JWT authentication (Bearer token) on all data and mutation
endpoints. Tokens are obtained from `POST /auth/login` and sent as
`Authorization: Bearer <token>`. In development without `AUTH_PASSWORD`
configured, auth is bypassed for convenience; in production a valid token is
always required.

Additional public endpoints (no JWT): `GET /`, `GET /health/ready`,
`GET /health/cache`, `GET /auth/status`, `POST /config/setup`. The WebSocket
endpoint (`/ws`) authenticates via a `token` query parameter. The Obsidian
webhook (`/webhook/obsidian`) authenticates via a shared secret or JWT fallback.

---

## 2. Endpoints

Each table lists the method, path, whether JWT auth is required, a brief
description, the request body (if any), and the response shape. See the
interactive OpenAPI docs at `/docs` for full schemas.

### 2.1 Health & Root

| Method | Path | Auth | Description | Request Body | Response |
|--------|------|------|-------------|--------------|----------|
| GET | `/` | No | Basic API info | — | `{name, version, docs}` |
| GET | `/health` | No | Liveness check | — | `{status, service}` |
| GET | `/health/ready` | No | Readiness check (DB, cache, AI service) | — | `{status, checks}` |
| GET | `/health/cache` | No | Cache performance metrics | — | cache stats object |
| GET | `/debug` | Yes | Safe diagnostic info (counts, cache, recent failures) | — | debug object |

### 2.2 Auth (`auth.py`)

| Method | Path | Auth | Description | Request Body | Response |
|--------|------|------|-------------|--------------|----------|
| POST | `/auth/login` | No | Single-user login; returns JWT | `{password, username}` (JSON body) | `{access_token, token_type}` |
| GET | `/auth/status` | No | Whether auth is configured | — | `{enabled}` |

### 2.3 Notes (`notes.py`)

| Method | Path | Auth | Description | Request Body | Response |
|--------|------|------|-------------|--------------|----------|
| GET | `/notes/` | Yes | List notes (filters: `tag`, `source_path`, `skip`, `limit`) | — | `List[Note]` |
| POST | `/notes/search/semantic` | Yes | Semantic search over embeddings (pgvector cosine similarity) | `{query, limit?, threshold?}` | `{results: [{note, score}]}` |
| GET | `/notes/{note_id}` | Yes | Get a single note | — | `Note` |
| POST | `/notes/` | Yes | Create a note (201) | `{title, content, tags, source, source_path}` | `Note` + `gamification` |
| PUT | `/notes/{note_id}` | Yes | Update a note | `{title?, content?, tags?, source_path?, source?}` | `Note` + `gamification` |
| DELETE | `/notes/{note_id}` | Yes | Delete a note (204) | — | — |
| POST | `/notes/rebuild-derived` | Yes | Rebuild tag co-occurrences & skills (202) | — | `{status}` |
| POST | `/notes/bulk-delete` | Yes | Delete multiple notes | `{ids: [int]}` | `{deleted, total}` |
| POST | `/notes/bulk-tag` | Yes | Add tags to multiple notes | `{ids: [int], tags: [str]}` | `{added, notes, tags}` |
| POST | `/notes/bulk-untag` | Yes | Remove tags from multiple notes | `{ids: [int], tags: [str]}` | `{removed, notes, tags}` |
| POST | `/notes/{note_id}/accept-tag` | Yes | Accept an AI-suggested tag (`tag_name` query) | — | `{tag, gamification}` |
| GET | `/notes/{note_id}/backlinks` | Yes | Notes linking to this note | — | `List[Note]` |
| GET | `/notes/{note_id}/similar` | Yes | Semantically similar notes (pgvector cosine similarity, `limit` query) | — | `List[{note, score}]` |
| POST | `/notes/embeddings/retry-failed` | Yes | Retry failed embeddings (`limit` query) | — | `{queued, remaining_failures}` |
| GET | `/notes/embeddings/dead-letters` | Yes | List dead-lettered embedding failures (`limit` query) | — | list of failure entries |
| POST | `/notes/embeddings/dead-letters/{note_id}/reset` | Yes | Reset a dead letter for retry | — | `{status, note_id}` |
| DELETE | `/notes/embeddings/dead-letters` | Yes | Purge all dead letters | — | `{purged}` |

### 2.4 Tags (`tags.py`)

| Method | Path | Auth | Description | Request Body | Response |
|--------|------|------|-------------|--------------|----------|
| GET | `/tags/` | Yes | List all tags with note counts | — | `List[{id, name, parent_id, note_count}]` |
| POST | `/tags/` | Yes | Create a tag (201) | `{name, parent_id?}` | `{id, name, parent_id}` |
| PUT | `/tags/{tag_id}/parent` | Yes | Set/clear a tag's parent (`parent_id` query) | — | `{id, name, parent_id}` |
| GET | `/tags/graph` | Yes | Knowledge graph (tags, notes, links, co-occurrences) | — | `{nodes, edges}` |

### 2.5 Goals (`goals.py`)

| Method | Path | Auth | Description | Request Body | Response |
|--------|------|------|-------------|--------------|----------|
| GET | `/goals/` | Yes | List goals (`skip`, `limit`) | — | `List[Goal]` |
| GET | `/goals/streak` | Yes | Goal completion streak | — | `{current_streak, best_streak}` |
| POST | `/goals/` | Yes | Create a goal (201) | `GoalCreate` | `Goal` |
| GET | `/goals/{goal_id}` | Yes | Get a single goal | — | `Goal` |
| PUT | `/goals/{goal_id}` | Yes | Update a goal | `GoalUpdate` | `Goal` |
| GET | `/goals/{goal_id}/content` | Yes | Get goal content (vault file or DB) | — | goal content object |
| POST | `/goals/{goal_id}/content` | Yes | Save goal content (vault + DB) | `GoalContent` | `Goal` |
| POST | `/goals/{goal_id}/complete` | Yes | Mark goal complete; awards XP | — | `{goal, gamification}` |
| DELETE | `/goals/{goal_id}` | Yes | Delete a goal (204) | — | — |
| POST | `/goals/{goal_id}/resolve-removal` | Yes | Resolve pending removal | `{action: "delete"|"manual"|"cancel"}` | `Goal` or `{status}` |

### 2.6 Gamification (`gamification.py`)

| Method | Path | Auth | Description | Request Body | Response |
|--------|------|------|-------------|--------------|----------|
| GET | `/gamification/stats` | Yes | XP, streak, plant stage stats | — | stats object |
| GET | `/gamification/streak-history` | Yes | Daily XP history (`days` query, default 30) | — | `List[{date, xp}]` |
| GET | `/gamification/recent-events` | Yes | Recent XP events (`limit` query) | — | `List[{type, xp, at}]` |
| POST | `/gamification/ping` | Yes | Register daily activity; awards XP | — | gamification result |

### 2.7 Personal Streaks (`personal_streaks.py`)

| Method | Path | Auth | Description | Request Body | Response |
|--------|------|------|-------------|--------------|----------|
| GET | `/personal-streaks/categories` | Yes | List available categories | — | `List[str]` |
| GET | `/personal-streaks/stats` | Yes | Global streak statistics | — | stats object |
| GET | `/personal-streaks/` | Yes | List streaks (`include_archived`, `category`, `include_history`, `days_history`) | — | `List[Streak]` |
| POST | `/personal-streaks/` | Yes | Create a streak (201) | `StreakCreate` | `Streak` |
| PUT | `/personal-streaks/{streak_id}` | Yes | Update a streak | `StreakUpdate` | `Streak` |
| DELETE | `/personal-streaks/{streak_id}` | Yes | Delete a streak (204) | — | — |
| POST | `/personal-streaks/{streak_id}/checkin` | Yes | Check in for today | `{note?, mood?, check_date?}` | `Streak` |
| DELETE | `/personal-streaks/{streak_id}/checkin` | Yes | Undo today's check-in | — | `Streak` |
| POST | `/personal-streaks/{streak_id}/freeze` | Yes | Use a freeze to protect the streak | — | `Streak` |
| GET | `/personal-streaks/{streak_id}/history` | Yes | Check-in history (`days` query) | — | `List[{date, note, mood, created_at}]` |

### 2.8 Skills (`skills.py`)

| Method | Path | Auth | Description | Request Body | Response |
|--------|------|------|-------------|--------------|----------|
| GET | `/skills/` | Yes | List skills (derived from tags) | — | `List[Skill]` |
| GET | `/skills/tree` | Yes | Skill tree (nodes + edges) | — | `{nodes, edges}` |
| POST | `/skills/sync` | Yes | Sync skills with tags | — | `{synced, updates}` |

### 2.9 Planning (`planning.py`)

| Method | Path | Auth | Description | Request Body | Response |
|--------|------|------|-------------|--------------|----------|
| GET | `/planning/assignments` | Yes | Get goal assignments for a date (`date` query, YYYY-MM-DD) | — | `{date, goal_ids}` |
| POST | `/planning/assignments` | Yes | Set goal assignments for a date | `{date, goal_ids}` | `{date, goal_ids}` |

### 2.10 Export (`export.py`)

| Method | Path | Auth | Description | Request Body | Response |
|--------|------|------|-------------|--------------|----------|
| GET | `/export/notes/markdown` | Yes | Export all notes as one markdown file | — | `text/markdown` (attachment) |
| GET | `/export/notes/html` | Yes | Export all notes as one HTML file | — | `text/html` (attachment) |
| GET | `/export/notes/zip` | Yes | Export all notes as individual `.md` in a ZIP | — | `application/zip` (attachment) |

### 2.11 Folders (`folders.py`)

| Method | Path | Auth | Description | Request Body | Response |
|--------|------|------|-------------|--------------|----------|
| POST | `/folders/` | Yes | Create a folder in the vault | `{path}` | `{status, path}` |
| DELETE | `/folders/{path:path}` | Yes | Delete a folder from the vault | — | `{status}` |

### 2.12 Metrics (`metrics.py`)

| Method | Path | Auth | Description | Request Body | Response |
|--------|------|------|-------------|--------------|----------|
| GET | `/metrics` | Yes | Prometheus-format metrics | — | `text/plain` (Prometheus) |

### 2.13 Push Notifications (`push.py`)

| Method | Path | Auth | Description | Request Body | Response |
|--------|------|------|-------------|--------------|----------|
| GET | `/push/vapid-public-key` | Yes | VAPID public key for web push | — | `{publicKey}` |
| POST | `/push/subscribe` | Yes | Subscribe to push notifications | `{endpoint, keys}` | `{status}` |
| POST | `/push/unsubscribe` | Yes | Unsubscribe from push notifications | — | `{status}` |
| POST | `/push/test` | Yes | Send a test push notification | `{title, body}` | `{status}` |

### 2.14 Stats (`stats.py`)

| Method | Path | Auth | Description | Request Body | Response |
|--------|------|------|-------------|--------------|----------|
| GET | `/stats/system` | Yes | System-wide counts (notes, tags, goals, skills, XP) | — | stats object |
| GET | `/stats/activity` | Yes | Daily activity for last N days (`days` query, default 30) | — | `{days: [{date, notes_created, xp_events}]}` |

### 2.15 Upload (`upload.py`)

| Method | Path | Auth | Description | Request Body | Response |
|--------|------|------|-------------|--------------|----------|
| POST | `/upload/image` | Yes | Upload an image (multipart `file`) | `file` (form) | `{url, filename, mime, size}` |
| POST | `/upload/file` | Yes | Upload an attachment (multipart `file`) | `file` (form) | `{url, filename, mime, size}` |

### 2.16 WebSocket (`websocket.py`)

| Method | Path | Auth | Description | Request Body | Response |
|--------|------|------|-------------|--------------|----------|
| WS | `/ws` | Token (query) | Real-time updates (note created/updated, XP, streak) | ping/pong JSON | broadcast JSON messages |

### 2.17 Vault (`vault.py`)

| Method | Path | Auth | Description | Request Body | Response |
|--------|------|------|-------------|--------------|----------|
| POST | `/vault/write-daily` | Yes | Trigger daily notes file write | — | `{status, file}` |
| POST | `/vault/write-objectives` | Yes | Trigger objectives file write | — | `{status}` |
| POST | `/vault/write-skills` | Yes | Trigger skills file write | — | `{status}` |

### 2.18 AI (`ai.py`)

| Method | Path | Auth | Description | Request Body | Response |
|--------|------|------|-------------|--------------|----------|
| POST | `/ai/classify` | Yes | Classify a note and suggest tags (proxied to AI service) | `{note_id, content, existing_tags}` | `{note_id, status, suggestions}` |
| GET | `/ai/usage` | Yes | AI usage and estimated cost | — | `{ai_enabled, estimated_cost_usd}` |
| POST | `/ai/cluster` | Yes | Cluster notes by semantic similarity (`eps`, `min_samples`, `max_notes` queries) | — | `{clusters, total_notes}` |
| POST | `/ai/daily-recap` | Yes | Generate an AI daily recap (`target_date` query, YYYY-MM-DD) | — | recap object |
| POST | `/ai/chat` | Yes | Conversational AI assistant (forwards context + messages to AI service) | `{messages: [{role, content}]}` | chat response object |

### 2.19 Sync (`sync.py`)

| Method | Path | Auth | Description | Request Body | Response |
|--------|------|------|-------------|--------------|----------|
| GET | `/sync/conflicts` | Yes | List notes with unresolved sync conflicts | — | `{conflicts, count}` |
| POST | `/sync/resolve/{note_id}` | Yes | Resolve a sync conflict | `{resolution, merged_content?}` | resolution result |

### 2.20 Obsidian Webhook (`obsidian.py`)

| Method | Path | Auth | Description | Request Body | Response |
|--------|------|------|-------------|--------------|----------|
| POST | `/webhook/obsidian` | Secret/JWT | Receive Obsidian change notifications | `{event, path, content?, mtime?}` | sync result |
| POST | `/webhook/obsidian/legacy` | Secret/JWT | Legacy webhook (records sync state only) | `{note_id, remote_mtime?}` | `{status, note_id, conflict}` |

### 2.21 Config (`config.py`)

| Method | Path | Auth | Description | Request Body | Response |
|--------|------|------|-------------|--------------|----------|
| GET | `/config` | Yes | Current config (public values only) | — | `ConfigResponse` |
| POST | `/config` | Yes | Update config (writes to `.env`) | `ConfigUpdate` | `{status, message}` |
| GET | `/config/keys` | Yes | List available config keys | — | `{keys: [...]}` |
| GET | `/config/gamification` | Yes | Gamification config (XP table, plant stages, milestones) | — | `GamificationConfig` |
| GET | `/config/setup-status` | No | Whether initial setup is needed | — | `{needs_setup}` |
| POST | `/config/setup` | No | Perform initial setup (set password, secret, vault path) | `{auth_password, obsidian_vault_path?}` | `{status, message}` |

### 2.22 Integrations — GitHub (`integrations/github.py`)

| Method | Path | Auth | Description | Request Body | Response |
|--------|------|------|-------------|--------------|----------|
| GET | `/integrations/github/status` | Yes | Connection status | — | `{connected, username}` |
| GET | `/integrations/github/user` | Yes | Authenticated GitHub user | — | GitHub user object |
| GET | `/integrations/github/repos` | Yes | List user repos (`per_page`, `sort`) | — | `{repos: [...]}` |
| GET | `/integrations/github/repos/{owner}/{repo}` | Yes | Get a single repo | — | repo object |
| POST | `/integrations/github/repos/db` | Yes | Track a repo in DB (`full_name` query) | — | `{id, full_name, status}` |
| GET | `/integrations/github/repos/db` | Yes | List tracked repos | — | `{repos: [...]}` |
| DELETE | `/integrations/github/repos/db/{repo_id}` | Yes | Stop tracking a repo | — | `{status, repo_id}` |
| GET | `/integrations/github/issues` | Yes | List issues (`state`, `filter`, `per_page`) | — | `{issues, stats, filter}` |
| GET | `/integrations/github/pulls` | Yes | List pull requests (`state`, `filter`, `per_page`) | — | `{pulls, stats, filter}` |
| GET | `/integrations/github/repos/{owner}/{repo}/issues` | Yes | List repo issues | — | `{issues: [...]}` |
| GET | `/integrations/github/repos/{owner}/{repo}/issues/{issue_number}` | Yes | Get a single issue | — | issue object |
| POST | `/integrations/github/repos/{owner}/{repo}/issues` | Yes | Create an issue (`title`, `body`, `labels` query) | — | `{id, number, title, url, state}` |
| PATCH | `/integrations/github/repos/{owner}/{repo}/issues/{issue_number}` | Yes | Update an issue | — | `{id, number, title, state}` |
| POST | `/integrations/github/repos/{owner}/{repo}/issues/{issue_number}/close` | Yes | Close an issue | — | `{number, state}` |
| GET | `/integrations/github/repos/{owner}/{repo}/issues/{issue_number}/comments` | Yes | List issue comments | — | `{comments: [...]}` |
| POST | `/integrations/github/repos/{owner}/{repo}/issues/{issue_number}/comments` | Yes | Add a comment (`body` query) | — | `{id, body}` |
| GET | `/integrations/github/repos/{owner}/{repo}/pulls` | Yes | List repo pull requests | — | `{pulls: [...]}` |
| GET | `/integrations/github/repos/{owner}/{repo}/commits` | Yes | List repo commits | — | `{commits: [...]}` |
| GET | `/integrations/github/db/items` | Yes | List tracked items (`repo_id`, `goal_id`) | — | `{items: [...]}` |
| POST | `/integrations/github/db/items/{item_id}/link-goal` | Yes | Link an item to a goal (`goal_id` query) | — | `{item_id, goal_id}` |
| DELETE | `/integrations/github/db/items/{item_id}/link-goal` | Yes | Unlink an item from a goal | — | `{item_id, goal_id}` |
| GET | `/integrations/github/db/events` | Yes | List webhook events (`repo_id`, `limit`) | — | `{events: [...]}` |
| POST | `/integrations/github/webhook` | Yes | Receive GitHub webhook events | webhook payload | `{status, event_id}` |
| POST | `/integrations/github/sync/repo/{repo_id}` | Yes | Sync a tracked repo's issues into DB | — | `{repo_id, synced, last_synced_at}` |
| GET | `/integrations/github/oauth/device/start` | Yes | Start GitHub Device Flow OAuth | — | device flow params |
| POST | `/integrations/github/oauth/device/polling` | Yes | Poll device code for token (`device_code` query) | — | `{status, access_token?}` |
| GET | `/integrations/github/oauth/web/start` | Yes | Start GitHub Web Flow OAuth | — | `{authorize_url, redirect_uri}` |
| GET | `/integrations/github/oauth/callback` | Yes | GitHub OAuth callback (`code` query) | — | `{status, access_token, ...}` |
| POST | `/integrations/github/oauth/revoke` | Yes | Revoke GitHub token (`token` query) | — | `{status}` |
| GET | `/integrations/github/oauth/scopes` | Yes | List configured OAuth scopes | — | `{scopes: [...]}` |

### 2.23 Integrations — Google (`integrations/google.py`)

| Method | Path | Auth | Description | Request Body | Response |
|--------|------|------|-------------|--------------|----------|
| GET | `/integrations/google/auth` | Yes | Google OAuth consent URL | — | `{url}` |
| GET | `/integrations/google/callback` | Yes | Google OAuth callback (`code`, `error` query) | — | token object |
| POST | `/integrations/google/connect` | Yes | Exchange code and persist tokens | `{code, scope?}` | token object |
| GET | `/integrations/google/status` | Yes | Connection status | — | status object |
| POST | `/integrations/google/disconnect` | Yes | Disconnect Google | — | status object |
| GET | `/integrations/google/calendars` | Yes | List calendars | — | calendars list |
| GET | `/integrations/google/calendars/{calendar_id}/events` | Yes | List calendar events | — | events list |
| GET | `/integrations/google/tasks` | Yes | List Google Tasks | — | tasks list |
| GET | `/integrations/google/gmail` | Yes | List Gmail messages | — | messages list |
| GET | `/integrations/google/contacts` | Yes | List Google Contacts | — | contacts list |

### 2.24 Integrations — Spotify (`integrations/spotify.py`)

| Method | Path | Auth | Description | Request Body | Response |
|--------|------|------|-------------|--------------|----------|
| GET | `/integrations/spotify/auth` | Yes | Spotify OAuth consent URL | — | `{url}` |
| GET | `/integrations/spotify/callback` | Yes | Spotify OAuth callback (`code`, `error` query) | — | token object |
| GET | `/integrations/spotify/recently-played` | Yes | Recently played tracks (`token`, `limit`) | — | tracks list |
| GET | `/integrations/spotify/top-tracks` | Yes | Top tracks (`token`, `limit`) | — | tracks list |
| GET | `/integrations/spotify/playlists` | Yes | User playlists (`token`) | — | playlists list |

### 2.25 Integrations — Strava (`integrations/strava.py`)

| Method | Path | Auth | Description | Request Body | Response |
|--------|------|------|-------------|--------------|----------|
| GET | `/integrations/strava/auth` | Yes | Strava OAuth consent URL | — | `{url}` |
| GET | `/integrations/strava/callback` | Yes | Strava OAuth callback (`code`, `error` query) | — | token object |
| GET | `/integrations/strava/activities` | Yes | Recent activities (`token`, `per_page`) | — | activities list |
| GET | `/integrations/strava/athlete` | Yes | Athlete profile (`token`) | — | athlete object |

---

## 3. Data Models

### Note
```python
class Note(Base):
    id: int
    title: str (max 500)
    content: str (Text)
    source: str ("joidy" | "obsidian" | "api" | "import")
    source_path: str | None (max 1000)
    is_embedded: bool
    created_at: datetime
    updated_at: datetime
    tags: list[NoteTag]
```

### Goal
```python
class Goal(Base):
    id: int
    title: str
    description: str
    temporality: str ("DAILY" | "WEEKLY" | "MONTHLY" | "ANNUAL")
    measurement_type: str ("COUNT" | "BOOLEAN" | "PERCENT")
    target_value: float
    current_value: float
    state: str ("ACTIVE" | "COMPLETED" | "FAILED" | "PAUSED" | "CANCELLED")
    fail_config: str ("STATIC" | "ROLLOVER" | "SNOWBALL")
    fail_emoji: str
    color: str
    theme: str
    note_id: int | None
    tag_id: int | None
    parent_id: int | None
    max_assignment_days: int | None
    pending_removal: bool
    is_completed: bool
    completed_at: datetime | None
    source_path: str | None
    created_at: datetime
    updated_at: datetime
```

### GamificationStats
```python
class GamificationStats(BaseModel):
    total_xp: int
    current_streak: int
    longest_streak: int
    plant_stage: int
    plant_stage_name: str
    next_stage_xp: int | None
    xp_to_next_stage: int | None
    last_activity_date: str | None
```

---

## 4. HTTP Response Codes

| Code | Meaning |
|--------|-------------|
| 200 | OK |
| 201 | Created |
| 202 | Accepted (async) |
| 204 | No Content |
| 400 | Bad Request |
| 401 | Unauthorized |
| 404 | Not Found |
| 409 | Conflict |
| 413 | Payload Too Large |
| 422 | Validation Error |
| 500 | Internal Server Error |
| 502 | Bad Gateway (upstream error) |
| 503 | Service Unavailable |

---

## 5. Errors

Standard error format:

```json
{
  "detail": "Description of the error"
}
```

---

## 6. Rate Limiting

The AI service implements rate limiting. See `ai-service/rate_limiter.py`.
The API also applies a `RateLimitMiddleware` (see `api/middleware/rate_limit.py`).
