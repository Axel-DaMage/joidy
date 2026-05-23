# Joidy — Agent Instructions

## Project Overview

Monorepo with 4 Docker services for a personal knowledge management system with gamification:

| Service | Framework | Port | Purpose |
|---------|-----------|------|---------|
| `frontend/` | SvelteKit + Vite + TypeScript | 3000 | Web UI |
| `api/` | FastAPI (Python 3.12) | 8000 | REST API |
| `ai-service/` | FastAPI + Gemini | 8002 | AI embeddings & classification |
| `worker/` | Python asyncio | 8001 | Background tasks (vault watcher, daily writes) |

Database: SQLite with `sqlite-vec` for vector embeddings at `./data/db/joidy.db`

## Essential Commands

### Development Workflow
```bash
make setup           # First-time: copy .env.example → .env, create data dirs
make dev             # Start all services with hot reload (Ctrl+C to stop)
make dev-d           # Start detached (background)
make dev-reset       # Full reset: remove volumes + recreate from scratch
make stop            # Stop all services
make build           # Rebuild all Docker images (no cache)
```

### Debugging & Inspection
```bash
make logs            # Tail logs from all services
make logs-api        # API logs only
make logs-ai         # AI service logs only
make logs-worker     # Worker logs only

make shell-api       # Exec into API container (bash)
make shell-worker   # Exec into worker container (bash)

make db-health       # Verify DB tables exist and migrations applied
```

### Debug Endpoints
- **API debug:** `http://localhost:8000/debug` — Detailed system info (DB stats, cache, gamification, recent errors)
- **Health check:** `http://localhost:8000/health/ready` — Comprehensive service health

### Database & Migrations
```bash
make migrate         # Run Alembic migrations to head (in api container)
```

### Testing
```bash
# API unit tests (specific test files)
make test-api

# Single test file
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm api \
  sh -c "PYTHONPATH=/app python -m unittest tests.test_embedding_retry"

# Frontend typecheck
cd frontend && npm run check
```

## Environment Setup

**Required in `.env`:**
```bash
GEMINI_API_KEY           # From https://aistudio.google.com/ — required for AI features
OBSIDIAN_VAULT_PATH      # Absolute path to Obsidian vault on host (mounts to /vault in worker)
SECRET_KEY               # Session signing key — generate with: openssl rand -hex 32
```

**Optional:**
```bash
GITHUB_CLIENT_ID / GITHUB_CLIENT_SECRET   # For GitHub OAuth
GITHUB_TOKEN / GITHUB_USERNAME           # For GitHub sync
TELEGRAM_BOT_TOKEN                       # For Telegram bot (leave empty to disable)
```

**Port overrides** (if 3000, 8000, 8001, 8002 conflict):
```bash
FRONTEND_PORT=3001
API_PORT=8001
# etc.
```

## Dev Workflow

1. **First time:** `make setup` → edit `.env` with your keys
2. **Start dev:** `make dev` — services auto-reload on file changes
3. **API docs:** http://localhost:8000/docs
4. **Frontend:** http://localhost:3000

**File watching:**
- `api/` → uvicorn `--reload` on `/app` mount
- `worker/` → Python restarts on `/app` mount
- `frontend/` → Vite HMR on `/app` mount
- `ai-service/` → uvicorn `--reload` on `/app` mount

## Architecture Notes

### API Structure
```
api/
├── main.py           # FastAPI app, router registration, CORS, middleware
├── config.py         # Pydantic Settings (env vars)
├── database.py       # SQLAlchemy engine, SQLite + sqlite-vec setup, init_db()
├── models/           # SQLAlchemy ORM models (note.py, tag.py, skill.py, goal.py, gamification.py, github.py, planning.py)
├── routers/         # FastAPI routers (notes, tags, skills, goals, gamification, personal_streaks, vault, ai, planning, integrations/github)
├── services/        # Business logic (embedding_service, gamification_engine, tag_graph, skill_tree, note_service, goal_service, github_service, etc.)
├── alembic/         # Database migrations
│   └── versions/    # Migration files (initial_schema, embedding_failures, tag_cooccurrences, planning, github_integration)
└── tests/           # Unit tests (unittest)
```

**Pattern:** Routers call service functions. Service functions handle business logic and DB operations.

### Worker Structure
```
worker/
├── main.py           # Entry point: runs watch_vault() + schedule_daily_writes() concurrently
├── config.py         # Pydantic Settings
├── watchers/
│   └── vault_watcher.py   # Monitors /vault for .md changes, imports to API, debounced 2s
└── tasks/
    └── joidy_daily_writer.py  # Writes daily summaries to vault/_joidy/
```

### AI Service Structure
```
ai-service/
├── main.py           # FastAPI app with /embed, /classify, /rag endpoints
├── gemini_client.py  # Google Gemini API wrapper
├── config.py         # Pydantic Settings (GEMINI_API_KEY)
├── database.py       # Read-only DB access for RAG queries
├── rate_limiter.py   # API rate limiting
└── cost_tracker.py  # Usage tracking
```

### Frontend Structure
```
frontend/
├── src/
│   ├── routes/      # SvelteKit pages (notes, goals, streaks, skills, graph, +layout)
│   ├── lib/
│   │   ├── stores/  # Svelte stores (notes, gamification, pomodoro, graph, settings, etc.)
│   │   ├── api.ts   # API client wrapper
│   │   └── utils/   # Utilities (fileTree, userSettings)
│   └── app.html     # Entry HTML
├── package.json     # npm scripts: dev, build, check
├── vite.config.ts   # Vite + SvelteKit config, HMR settings for Docker
└── svelte.config.js # SvelteKit adapter-node config
```

### Database Schema
- **Notes:** id, title, content, source, source_path, created_at, updated_at
- **Tags:** id, name, created_at
- **NoteTags:** note_id, tag_id (junction table)
- **TagCooccurrences:** tag_a_id, tag_b_id, weight (precomputed)
- **Skills:** id, name, parent_id (tree structure), xp_needed, icon
- **Goals:** id, title, target_date, completed, created_at
- **UserStats:** id=1 (singleton), total_xp, current_streak, plant_stage, last_activity_date
- **XPEvents:** event_type, xp, metadata_json, created_at
- **StreakRecords:** activity_date, xp_earned
- **EmbeddingFailures:** note_id, attempts, last_error, next_retry_at
- **Planning entries:** for scheduling/content generation

### Internal Communication
- **API → AI:** HTTP to `http://ai-service:8002`
- **API → Worker:** HTTP to `http://worker:8001`
- **Worker → API:** HTTP to `http://api:8000`
- **Worker → Vault:** Reads files from `/vault` mount (OBSIDIAN_VAULT_PATH on host)

### Gamification System
Located in `api/services/gamification_engine.py`:
- **XP Events:** note_created (+10), note_edited (+5), tag_added (+3), topic_connected (+8), goal_completed (+50), daily_activity (+15)
- **Streak Milestones:** 7, 30, 100, 365 days → +100 XP each
- **Plant Stages:** seed → sprout → seedling → young → mature → flowering → tree (based on total XP thresholds)
- **Grace Period:** 1 missed day forgiven per week
- Process via `process_event(db, event_type, metadata)` → returns `GamificationResult`

## Testing

### Running Tests
```bash
# All configured tests
make test-api

# Single test
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm api \
  sh -c "PYTHONPATH=/app python -m unittest tests.test_embedding_retry"

# Frontend typecheck
cd frontend && npm run check
```

### Test Files
- `api/tests/test_embedding_retry.py` — Exponential backoff logic
- `api/tests/test_gamification_config.py` — XP table parsing, plant stage thresholds
- `api/tests/test_tag_graph_service.py` — Co-occurrence rebuild logic
- `api/tests/test_skill_tree_service.py` — Skill tree operations

### Frontend Testing
```bash
cd frontend && npm run check  # svelte-check (typecheck)
```

## Known Issues (from TODO.md)

1. **CORS allows "*" in production** — Security concern, needs configuration
2. **Embeddings retry inconsistent** — `EmbeddingFailure` retry logic may have edge cases
3. **Skill tree can have cycles** — If circular parent hierarchies created manually
4. **Vault watcher** — Can leave orphaned tasks in edge cases
5. **Response cache empty** — `api/services/response_cache.py` is placeholder
6. **Tag co-occurrences O(n²)** — Should pre-calculate on write, uses `tag_cooccurrences` table

## Development Quirks

### SQLite + sqlite-vec
The API uses `sqlite-vec` for vector embeddings. Loaded via:
```python
dbapi_connection.enable_load_extension(True)
sqlite_vec.load(dbapi_connection)
```
Enabled in `database.py:_setup_sqlite()`.

### Alembic Migrations
Run with: `make migrate` or inside container:
```bash
docker compose exec api alembic -c /app/alembic.ini upgrade head
```

### Docker Volumes (dev)
- `./api:/app` — API source code (hot reload)
- `./worker:/app` — Worker source code (hot reload)
- `./frontend:/app` — Frontend source code (hot reload)
- `./data/db:/data/db` — SQLite database shared across all services
- `${OBSIDIAN_VAULT_PATH}:/vault` — Obsidian vault (worker read-only)

### Environment Variable Precedence
- `.env` file loaded by Pydantic Settings
- Docker Compose environment overrides
- Command-line arguments (e.g., `API_PORT=8001 make dev`)

### Frontend Debug Tools (Dev Mode Only)
When **Dev Mode** is enabled in Settings, the frontend logs additional debug information:

**Module:** `frontend/src/lib/utils/debug.ts`
- `debugLog()`, `debugWarn()`, `debugError()` — logging only when dev mode is ON
- `debugGroup()` / `debugGroupEnd()` — group related log messages
- `captureAndLog()` — captures errors with stack traces
- Auto-captures uncaught errors and unhandled promise rejections

**Usage:**
```ts
import { debugLog, debugError } from '$lib/utils/debug';

debugLog('Variable state:', someVariable);
debugError('Something went wrong:', errorObject);
```

The endpoint `/debug` in the API provides:
- Timestamp, Python version, platform info
- DB stats (notes, tags, skills, goals, embedding failures)
- Cache stats
- Recent embedding failures
- Gamification stats (XP, streak, plant stage)

Access: `http://localhost:8000/debug`

## Key Files for Reference

| File | Purpose |
|------|---------|
| `Makefile` | All dev commands |
| `docker-compose.yml` | Service definitions, ports, env vars |
| `docker-compose.dev.yml` | Dev overrides (volumes, hot reload) |
| `api/main.py` | FastAPI app setup, router registration |
| `api/config.py` | Settings (database_url, ai_service_url, etc.) |
| `api/database.py` | SQLAlchemy setup, migrations |
| `api/services/gamification_engine.py` | XP, streaks, plant stages |
| `worker/main.py` | Background task orchestration |
| `worker/watchers/vault_watcher.py` | Obsidian file sync |
| `ai-service/main.py` | AI endpoints (embed, classify) |
| `frontend/package.json` | npm scripts |
| `frontend/vite.config.ts` | Vite config with Docker HMR fix |

## Pre-commit / Lint / Typecheck

Currently no configured lint/format scripts. For Python:
- `ruff` or `flake8` could be added to `api/requirements.txt`
- `black` for formatting

For frontend:
- `npm run check` runs `svelte-check` (type checking via tsconfig)
- No pre-commit hooks configured

## Code Style Conventions

- **Python:** snake_case variables, type hints, docstrings on services
- **Svelte:** PascalCase components, `<script lang="ts">`
- **API:** Pydantic models in routers, SQLAlchemy models in `models/`
- **Database:** Timestamps in UTC, foreign keys with `ON DELETE CASCADE`
- **Configuration:** All settings via environment (`.env`), no hardcoded values

## Important Constraints

1. **Never commit `.env`** — Already in `.gitignore`
2. **Never commit `data/`** — Already in `.gitignore`
3. **Database is shared** — All services write to `./data/db/joidy.db`
4. **Vault path must be absolute** — On host machine, not relative
5. **API must be healthy before other services start** — `depends_on: condition: service_healthy` in docker-compose
6. **GEMINI_API_KEY required** — AI features disabled without it, but API still works

## Development Mode (Active)

The project is currently in **Development Mode**. This means:

- **Features under development** are hidden by default
- **Enable dev mode** in Settings (Ajustes) → toggle "Modo Desarrollo" to ON
- **Pages in development** show "En Construcción" to regular users
- **With dev mode ON**, these pages show "En Desarrollo" with access to the actual implementation

### Workflow

1. **Default state (Production)**: Users see "En Construcción" on:
   - Habilidades (/skills)
   - Grafo de Notas (/graph)
   - IA (/ai)
   - Gmail (/gmail)
   - Contactos (/contactos)
   - Strava (/strava)
   - Spotify (/spotify)

2. **Dev Mode ON**: All features are visible and functional

3. **Development approach**:
   - All new work happens directly (no feature branches needed)
   - Keep dev mode ON while implementing features
   - Only push to production when explicitly told to do so
   - The agent will indicate when work is ready for "Production"

### Checking Dev Mode Status

The frontend stores this in localStorage under `joidy-dev-mode`. To verify:
- Open browser DevTools → Application → Local Storage
- Or check the Settings panel toggle

---

**IMPORTANT**: Continue working in Development Mode until instructed otherwise. Do not create separate branches for new features — work directly in the main codebase.
