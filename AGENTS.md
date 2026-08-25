# Joidy — Agent Instructions

4 Docker services, PostgreSQL 16 + `pgvector`, GPL v3.

## Services & Ports

| Service | Dir | Stack | Port |
|---------|-----|-------|------|
| `frontend` | `frontend/` | SvelteKit + Vite + TS | 3000 |
| `api` | `api/` | FastAPI (Python 3.12) | 8000 |
| `ai-service` | `ai-service/` | FastAPI + Gemini | 8002 |
| `worker` | `worker/` | Python asyncio | 8001 |

DB: PostgreSQL 16 (pgvector) in `postgres` container, volume `postgres_data`.
`DATABASE_URL=postgresql://joidy:joidy@postgres:5432/joidy`

## Essential Commands

```bash
make setup           # First-time: .env from .env.example, data dirs
make dev             # Start all services with hot reload (Ctrl+C)
make dev-d           # Start detached
make dev-reset       # Full reset: remove volumes, recreate
make stop            # Stop all
make logs[-api|-ai|-worker]
make shell-api       # Exec into api container
make db-health       # Verify DB tables + migrations applied
make migrate         # Alembic upgrade head (in api container)
make test            # test-api + test-frontend
make test-api        # PYTHONPATH=/app python -m unittest discover -s tests
make test-frontend   # cd frontend && npx playwright test
make lint            # python -m compileall on all Python services
```

Single test:
```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm api \
  sh -c "PYTHONPATH=/app python -m pytest tests/test_embedding_retry.py"
```

Frontend typecheck:
```bash
cd frontend && npm run check
```

## Required .env

```bash
GEMINI_API_KEY        # https://aistudio.google.com/
OBSIDIAN_VAULT_PATH   # Absolute host path to Obsidian vault
SECRET_KEY            # openssl rand -hex 32
```

Optional: `GITHUB_CLIENT_ID/SECRET/TOKEN/USERNAME`, `TELEGRAM_BOT_TOKEN`,
`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `COHERE_API_KEY`, `OLLAMA_BASE_URL`.

Port overrides: `FRONTEND_PORT`, `API_PORT`, `AI_SERVICE_PORT`, `WORKER_PORT`.


## Integrations Status

| Integration | Backend | Frontend | Issue |
|-------------|---------|----------|-------|
| **Gemini AI** | ✅ `ai-service` | ⚠️ Placeholder UI | #41 |
| **GitHub** | ✅ `auth/github` | ✅ Unified integrations page | #120 |
| **Google Calendar** | ⚠️ `integrations/google` scaffold | ⚠️ Partial | #2 |
| **Google Tasks** | ⚠️ `integrations/google` scaffold | ⚠️ Partial | #2 |
| **Gmail** | ❌ None (Google OAuth scaffold only) | ❌ None | #42 |
| **Contacts** | ❌ None (Google OAuth scaffold only) | ❌ None | #43 |
| **Strava** | ⚠️ `integrations/strava` scaffold | ❌ None | #44 |
| **Spotify** | ⚠️ `integrations/spotify` scaffold | ❌ None | #45 |

## Architecture

### API (`api/`)
```
main.py → routers/*.py → services/*.py → models/*.py
```
- **routers/**: HTTP endpoints, Pydantic validation only
- **services/**: Business logic + DB ops
- **models/**: SQLAlchemy ORM
- **alembic/versions/**: 7 migration files (`make migrate`)
- **tests/**: 31 test files (unittest)

Internal comms:
- API → AI: `http://ai-service:8002`
- API → Worker: `http://worker:8001`
- Worker → API: `http://api:8000`
- Worker → Vault: reads `/vault` (host: `OBSIDIAN_VAULT_PATH`)

### AI Service (`ai-service/`)
Factory pattern (`clients/`) for 6 providers (Gemini, OpenAI, Anthropic, Cohere, Ollama, OpenRouter). Endpoints: `/embed`, `/classify`, `/rag`.

### Worker
Two concurrent asyncio tasks: `watch_vault()` (watches `/vault/*.md`, 2s debounce) + `schedule_daily_writes()` (writes _joidy/ files at midnight).

### Frontend (`frontend/src/`)
- `routes/`: SvelteKit pages (notes, goals, graph, skills, streaks, ai, etc.)
- `lib/stores/`: 24 Svelte stores (notes, gamification, pomodoro, graph, settings, etc.)
- `lib/actions/`: Svelte actions (focusTrap, liquidGlass)
- `lib/api.ts`: API client wrapper
- `lib/components/`: Reusable Svelte components (Modal, DynamicIcon, GoalCard, StreakListItem, etc.)
- `lib/utils/logger.ts`: `logger.info()` / `logger.log()` / `logger.debug()` / `logger.warn()` / `logger.error()` — the logging convention used across the codebase (imported in 9+ files). Dev Mode is stored in localStorage key `joidy-dev-mode`, toggled in Settings. Pages under development show "En Construccion" unless dev mode is ON.

#### Icon Usage Convention (#257)
- **Static UI icons** (always the same icon, e.g. close button, search): Import directly from `lucide-svelte` — `import { Search, X } from 'lucide-svelte'`. This is tree-shakeable and more efficient.
- **Dynamic icons** (icon name comes from data/config, e.g. streak icon, folder icon, nav item icon): Use `<DynamicIcon name={iconName} />` — supports runtime lookup, kebab-to-PascalCase conversion, and icon pack switching (Lucide/Phosphor/Material).
- **Streak icons**: Use `<StreakIcon name={streak.icon} />` — optimized for streak items with emoji fallback.
- Never use `<DynamicIcon name="StaticName" />` with a hardcoded string — import the icon directly instead.

### Gamification
`api/services/gamification_engine.py`: XP events (note_created +10, note_edited +5, daily_activity +15, goal_completed +50), streaks (7/30/100/365d → +100 XP), plant stages (0→semilla, 300→brote, 1200→planton, 4000→joven, 10000→madura, 25000→floreciendo, 60000→arbol). Grace period: 1 missed day/week.

## Testing Quirks
- Uses `pytest` for API tests (`pytest` discover under `tests/`), with `unittest` style fixtures in `conftest.py`
- Single test: `PYTHONPATH=/app python -m unittest tests.test_file`
- Ruff config exists in `pyproject.toml` + `.pre-commit-config.yaml`, but pre-commit is not installed by default and CI does not run ruff. Run `ruff check` / `ruff format` manually if desired.
- CI: `compileall`, `unittest`, `npm run check`, `npm run build`, Docker build

## Known Issues (from code audit)
1. ~~CORS allows `*` in non-production~~ — **Fixed**: `_get_cors_origins()` in `api/main.py` respects `cors_allowed_origins` setting; dev fallback only. Same in `ai-service/main.py`.
2. Auth JWT is now enforced on all data/mutation endpoints (except `/auth/*`, `/config`, and `/ws`)
3. ~~Embedding retry has edge cases~~ — **Fixed**: `EmbeddingFailureRepository` dead-letter logic corrected (#612). `embedding_service.py` retry/dead-letter functions are correct and used by routers.
4. ~~Skill tree can have cycles if circular parent created manually~~ — **Fixed**: `set_parent` in `api/routers/tags.py` walks the parent chain and rejects circular references.
5. ~~Response cache is a placeholder~~ — **Fixed**: `api/services/response_cache.py` has a full TTL cache with stats, eviction, and registered clearers.
6. ~~Tag co-occurrences O(n²)~~ — **Fixed**: `api/services/tag_graph.py` pre-calculates co-occurrences on write via `sync_tag_cooccurrences_for_tags`, called on every note create/update/delete.
7. ~~Vault watcher can leave orphaned tasks~~ — **Fixed**: `worker/watchers/vault_watcher.py` has `PersistentEventLog` for crash recovery, `_in_flight` task tracking, graceful two-phase shutdown with `asyncio.shield`, and per-file locks.
8. ai-service `/cluster` endpoint had connection leak + SQL injection — **Fixed** (#610).
9. ai-service database engine missing `pool_pre_ping`/`pool_recycle` — **Fixed** (#611).

## System Install (AUR) vs Git Clone

`joidy` (the CLI in `scripts/joidy.sh`) resolves `PROJECT_DIR` to the install dir
(`/usr/share/joidy` for AUR, read-only) and its `.env` to `~/.config/joidy/.env`.
Compose resolves *relative* bind mounts against the compose file directory, so on a
system install `./.env` and `./data` pointed inside the read-only install dir:

- Missing `./.env` → Docker creates `/app/.env` as a **directory** → `read_env()` in
  `api/routers/config.py` raised `IsADirectoryError` → every `/config` request 500'd
  and the settings page broke. Guarded with `is_file()`; mount is now
  `${JOIDY_ENV_FILE:-./.env}`, exported by the CLI.
- `./data` root-owned → worker could not write its persistent event log
  (crash recovery disabled). Mount is now `${JOIDY_DATA_DIR:-./data}`; the CLI points
  it at `~/.local/share/joidy/data` when the install dir is not writable.

Consequence: the CLI's `.env` and the repo's `.env` are **different files**. They can
drift — notably `POSTGRES_PASSWORD`, which only applies at `initdb`. If the volume was
created with one password and the CLI later generates another, the API dies on startup
with `FATAL: password authentication failed for user "joidy"`. Fix without data loss:
`docker exec joidy-postgres-1 psql -U joidy -d joidy -c "ALTER USER joidy WITH PASSWORD '<env value>'"`
(local socket auth is `trust`, so this works even when TCP auth fails).

`DOCKER_GID` must match the group owning `/var/run/docker.sock` (`getent group docker`),
otherwise the API joins group 0, `/system/power/status` returns
`docker_available: false`, and Settings → Servicios shows "Docker no está disponible".
`joidy up` now autodetects it.

## Constraints
- Never commit `.env` or `data/` (in `.gitignore`)
- API must be healthy before other services start (`depends_on: condition: service_healthy`)
- AI features disabled without `GEMINI_API_KEY`; API still works
- Database is shared across all services (single PostgreSQL database via `DATABASE_URL`)
- Config via Pydantic `Settings` from `.env`; no hardcoded values
- `svelte-kit sync` runs on `postinstall` — can fail if `.svelte-kit/` has root-owned files (legacy only: since #886 the dev containers run as the host UID/GID via `docker-compose.dev.yml` build args + `user:`, so `make dev` never creates root-owned `.svelte-kit` and `make fix-permissions` no longer needs `sudo`).
- Vite HMR in Docker: `server.hmr.clientPort: 3000` + `host: 127.0.0.1` (in `vite.config.ts`, overridable via `JOIDY_HMR_HOST`). Using `localhost` breaks on hosts where it resolves to `::1` (IPv6) and Docker's IPv6 forwarding hangs.

## Workflow

- Base branch for pull requests is `development`. Always create feature branches from `development` and open PRs against `development`, not `main`.
- `main` is reserved for releases and should only be updated from `development` via release or hotfix PRs.

## Docker Rebuild After Pull (STRICT)

After **every** `git pull` (or merge that touches service code), the Docker images **MUST** be rebuilt from scratch before bringing services up. The `joidy up` CLI and `docker compose up -d` only consume pre-built images (`d4mag3/joidy-*:latest`) — they do **not** pick up source changes automatically. Running them without a rebuild means the containers serve stale code and fixes won't be visible.

### Mandatory rebuild sequence

```bash
# 1. Stop and remove current containers
joidy down

# 2. Rebuild ALL 4 production images from source (no cache, pull fresh base images)
#    Frontend MUST use --target production so it runs `node build` (not `vite dev`)
docker build --no-cache --pull -t d4mag3/joidy-frontend:latest --target production ./frontend
docker build --no-cache --pull -t d4mag3/joidy-api:latest        ./api
docker build --no-cache --pull -t d4mag3/joidy-ai-service:latest ./ai-service
docker build --no-cache --pull -t d4mag3/joidy-worker:latest     ./worker

# 3. Bring services up with the fresh images
joidy up
```

### Rules
- Dockerfiles use BuildKit cache mounts (`RUN --mount=type=cache`) — the host needs the `docker-buildx` package (Arch: `sudo pacman -S docker-buildx`) for local `docker build`. CI uses `docker/setup-buildx-action`, so no change needed there.
- **Never** run `joidy up` (or `docker compose up -d`) immediately after a pull without rebuilding first. The only exception is a pull that touches **only** docs, `.md` files, or files outside the 4 service directories.
- **Never** use `docker compose -f docker-compose.yml -f docker-compose.dev.yml build` to rebuild production images — the dev overlay forces the `development` Dockerfile target (Vite dev server), which is wrong for production and bakes dev-only config (e.g. `vite.config.ts` HMR host) into the image.
- The frontend production image requires `--target production` so the Dockerfile runs `npm run build` and serves the pre-compiled bundle with `node build` (SSR via `@sveltejs/adapter-node`).
- Data volumes (`postgres_data`, `data/`) are preserved across rebuilds — only the images and containers are recreated. No user data is lost.
- If only one service changed, you may rebuild just that image and `docker compose up -d --force-recreate <service>` to save time, but verify the other services are still on compatible images.

## CI Policy

GitHub Actions CI runs automatically for **all** pull requests, including forks and first-time contributors — no manual "Approve and run workflows" click is required (#811).

### Settings (configured in repo Settings → Actions → General)

- **Fork pull request workflows**: "Run workflows from fork pull requests **without approval**".
  - This setting has no REST API endpoint for public personal repositories; it must be set in the GitHub UI. Re-verify it after repository transfers or visibility changes.
- **Workflow permissions**: default `read` (least privilege), verified via `gh api repos/Axel-DaMage/joidy/actions/permissions/workflow`.
- **Allow GitHub Actions to create/approve PRs**: disabled (`can_approve_pull_request_reviews: false`).

### Workflow audit (safe for fork PRs)

The workflows that trigger on `pull_request` (`ci.yml`, `worker-tests.yml`) run in the **fork's context** — they have no access to repository secrets. This is the safe trigger for untrusted code.

Workflows that use secrets (`release.yml`, `publish.yml`) only trigger on `push: main`, `release: [published]`, or `workflow_dispatch` — never on pull requests. No workflow uses `pull_request_target` with secrets, so there is no injection vector from fork PRs.

### Branch protection (follow-up)

`development` should require status checks to pass before merge (all CI jobs: API Lint & Typecheck, Frontend Typecheck, Docker Build, Worker Tests) and require branches to be up to date. Linear history is not required (squash merge is fine).
