# API Service

FastAPI backend for Joidy — the main REST API handling notes, tags, goals,
skills, gamification, auth, and Obsidian sync. Runs on **port 8000**.

## Tech Stack

- Python 3.12, FastAPI, Uvicorn
- SQLAlchemy ORM + Pydantic v2, Alembic migrations
- PostgreSQL 16 + pgvector (shared database)
- JWT auth (GitHub OAuth device flow)

## Prerequisites

- Docker + Docker Compose (recommended) or Python 3.12 + `requirements.txt`
- A running PostgreSQL instance (the `postgres` container in dev)
- `.env` configured from `.env.example` (see root [AGENTS.md](../AGENTS.md))

## Development

From the repo root:

```bash
make dev          # all services, hot reload (Ctrl+C to stop)
make logs-api     # tail API logs
make shell-api    # exec into the api container
make migrate      # apply Alembic migrations
make db-health    # verify tables + migrations applied
```

Standalone container:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up api
```

## Environment Variables

Key vars (see root [`.env.example`](../.env.example) for the full list):

- `DATABASE_URL` — PostgreSQL connection string
- `SECRET_KEY` — JWT/session signing key
- `GEMINI_API_KEY` — enables AI features (optional; API works without it)
- `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` — GitHub OAuth
- `API_PORT` — override the default 8000

## Testing

```bash
make test-api     # from repo root
# or directly:
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm api pytest
```

Single test: `PYTHONPATH=/app python -m pytest tests/test_embedding_retry.py`

## Project Structure

```
api/
├── main.py            App entrypoint, router registration, middleware
├── config.py          Pydantic Settings (env-driven)
├── database.py        SQLAlchemy engine + session
├── routers/           HTTP endpoints (Pydantic validation only)
├── services/          Business logic + DB operations
├── models/            SQLAlchemy ORM models
├── middleware/        Correlation ID, request ID, rate limit, metrics
├── alembic/           Migrations (versions/ has 12 files)
├── repositories.py    Shared query helpers
└── tests/             pytest/unittest test suite
```

Request flow follows **Routers → Services → Models**: routers do only Pydantic
validation, services hold business logic and DB ops, models define the ORM.

## See Also

- [ARCHITECTURE.md](../ARCHITECTURE.md) — system overview and data flow
- [AGENTS.md](../AGENTS.md) — agent instructions, commands, known issues
- [docs/](../docs/) — architecture decision records and guides
