# Worker Service

Python asyncio background worker for Joidy. Handles Obsidian vault syncing and
scheduled daily writes. Runs on **port 8001** (healthcheck only — there is no
HTTP server).

## Tech Stack

- **Python 3.12**, asyncio
- `watchdog` for filesystem events
- HTTP calls to the `api` service (no inbound HTTP)

## Prerequisites

- Docker + Docker Compose (recommended)
- Or Python 3.12 with `requirements.txt` for local dev
- `OBSIDIAN_VAULT_PATH` pointing to a host vault (mounted at `/vault`)
- The `api` service must be reachable at `http://api:8000`

## Development

Start the full stack with hot reload from the repo root:

```bash
make dev          # all services, hot reload (Ctrl+C to stop)
make logs-worker  # tail worker logs only
```

To run the worker container alone:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up worker
```

## Environment Variables

Key variables consumed by this service (see root [`.env.example`](../.env.example)
for the full list — do not duplicate here):

- `OBSIDIAN_VAULT_PATH` — host path to the Obsidian vault (supports `~`, expanded by `joidy up`)
  (mounted read-only at `/vault` inside the container)
- `DATABASE_URL` — shared PostgreSQL connection
- `WORKER_PORT` — override the default 8001 (healthcheck only)

## Testing

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm worker pytest
```

## Tasks

The worker runs two concurrent asyncio tasks from `main.py`:

- **`watch_vault()`** — watches `/vault/*.md` for changes (2s debounce) and
  pushes new/updated notes to the API via `POST /notes`.
- **`schedule_daily_writes()`** — at midnight, writes daily summary files into
  the vault's `_joidy/` directory.

There is **no HTTP server** — the `:8001` port is used only by the Docker
healthcheck, which verifies the worker process is alive via a PID check.

## Project Structure

```
worker/
├── main.py                 Entrypoint: starts both asyncio tasks
├── config.py               Pydantic Settings (env-driven)
├── tasks/                  Scheduled / long-running tasks
│   └── joidy_daily_writer.py   Midnight daily-summary writer
├── watchers/               Filesystem watchers
│   └── vault_watcher.py        Obsidian vault change watcher (watchdog)
└── tests/                  Test suite
```

## See Also

- [Architecture](../docs/architecture.md) — system overview and data flow
- [AGENTS.md](../AGENTS.md) — agent instructions, commands, known issues
- [docs/](../docs/) — architecture decision records and guides
