# Architecture Decision Records (ADR)

This document records the major architectural decisions made in Joidy and the rationale behind them.

## ADR-001: SQLite as the primary database

**Status:** Superceded — The project now uses PostgreSQL 16 + pgvector in all environments. See `docker-compose.yml`.

**Context:** The project started as a personal knowledge management tool. It needed a zero-configuration database that could be shared across the API, AI service, and worker without requiring a separate process.

**Decision:** Use a single SQLite file (`./data/db/joidy.db`) with WAL mode enabled. Use `sqlite-vec` for vector similarity search instead of `pgvector`.

**Consequences:**
- Simplified local development and deployment.
- No external database process is required.
- The database file must be mounted into all service containers.
- Write concurrency is managed through WAL mode.

## ADR-002: Monorepo with Docker Compose

**Status:** Accepted

**Context:** Joidy consists of a frontend, an API, an AI service, and a worker. They share models, configuration patterns, and the PostgreSQL database.

**Decision:** Keep all services in a single repository and orchestrate them with Docker Compose.

**Consequences:**
- Easy to start the whole stack with `make dev`.
- Shared files such as `.env` and `data/` are mounted into containers.
- Production Compose uses pre-built images; development Compose adds bind mounts and hot reload.

## ADR-003: SvelteKit for the frontend

**Status:** Accepted

**Context:** The frontend needs a reactive UI with good TypeScript support, server-side rendering for the landing page, and a simple static export or Node adapter for containerized deployment.

**Decision:** Use SvelteKit with Vite and the Node adapter.

**Consequences:**
- Highly reactive UI with Svelte 5 runes.
- Fast dev server with HMR inside Docker.
- Service worker support for PWA/offline features.

## ADR-004: FastAPI for backend services

**Status:** Accepted

**Context:** The API and AI service need a Python framework with automatic OpenAPI documentation, dependency injection, and async support.

**Decision:** Use FastAPI for both the API and the AI service.

**Consequences:**
- OpenAPI docs available at `/docs`.
- Shared patterns for middleware, health checks, and configuration.
- Easy to test with `TestClient`.

## ADR-005: JWT-based authentication

**Status:** Accepted

**Context:** Joidy is a single-user application with optional integrations. It needs a lightweight auth mechanism that does not require a database session store.

**Decision:** Use stateless JWT tokens signed with `SECRET_KEY`. Authentication is enforced on data/mutation endpoints, while `/auth/*`, `/config`, and `/ws` remain public.

**Consequences:**
- No session store required.
- Tokens are short-lived and refreshed through the frontend.
- `SECRET_KEY` must be rotated in production.

## ADR-006: Gamification engine decoupled from CRUD

**Status:** Accepted

**Context:** Notes, goals, and tags are core entities, but gamification (XP, streaks, plant stages) is a cross-cutting concern.

**Decision:** Implement gamification in `api/services/gamification_engine.py` and trigger it from routers/services, not from models.

**Consequences:**
- Business logic is testable in isolation.
- Gamification rules can be changed without touching CRUD code.
- XP events are stored for analytics and streak calculations.
