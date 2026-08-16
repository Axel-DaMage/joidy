# Architecture Decision Records (ADR)

This directory contains all ADRs for the Joidy project. Each ADR documents a
significant architectural decision, its context, and its consequences.

## Index

| ADR | Title | Status |
|-----|-------|--------|
| [0001](0001-sveltekit-for-frontend.md) | SvelteKit for the Frontend | Accepted |
| [0002](0002-sqlite-for-development.md) | SQLite + sqlite-vec for Development | Superceded by 0004 |
| [0003](0003-jwt-authentication.md) | JWT Authentication | Accepted |
| [0004](0004-postgresql-pgvector.md) | PostgreSQL + pgvector as Primary Database | Accepted |
| [0005](0005-rate-limiting-strategy.md) | In-Memory Rate Limiting | Accepted |
| [0006](0006-websocket-realtime.md) | WebSocket for Real-Time Communication | Accepted |

## Format

All ADRs follow a consistent template with these sections:
- **Estado** (Status): Accepted / Superceded / Deprecated
- **Contexto** (Context): Why this decision was needed
- **Decisión** (Decision): What was decided
- **Consecuencias** (Consequences): Positive and negative impacts
- **Referencias** (References): Links to relevant resources

## How to Add a New ADR

1. Create a new file `NNNN-short-title.md` (zero-padded number)
2. Follow the template above
3. Add an entry to the index table in this README
