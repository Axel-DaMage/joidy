# Frontend Service

SvelteKit web application for Joidy — the user-facing dashboard for notes,
goals, streaks, skills, the knowledge graph, and AI features. Runs on
**port 3000**.

## Tech Stack

- SvelteKit + Vite + TypeScript, Svelte 5 runes (`$state`, `$derived`, `$effect`)
- CSS variables for theming, PWA support
- `lucide-svelte` icons, `vitest` for unit tests

## Prerequisites

- Docker + Docker Compose (recommended) or Node.js 20+ with `npm`
- The `api` service reachable at the URL in `VITE_API_URL`
- `.env` configured from `.env.example` (`VITE_API_URL=http://localhost:8000`)

## Development

From the repo root:

```bash
make dev          # all services, hot reload (Ctrl+C to stop)
```

Standalone: `cd frontend && npm install && npm run dev` (http://localhost:3000)

Or via Docker: `docker compose -f docker-compose.yml -f docker-compose.dev.yml up frontend`

## Environment Variables

- `VITE_API_URL` — base URL of the API service (see [`.env.example`](.env.example))
- `FRONTEND_PORT` — override the default 3000 (set in the root `.env`)

See root [`.env.example`](../.env.example) for service-wide variables.

## Testing

```bash
cd frontend
npm run check     # svelte-check type checking
npm run lint      # eslint
npm run test      # vitest unit tests
```

End-to-end (from repo root): `make test-frontend` (npx playwright test)

## Project Structure

```
frontend/
├── src/
│   ├── routes/           SvelteKit pages (notes, goals, graph, skills, streaks, ai, ...)
│   ├── lib/
│   │   ├── stores/       Svelte stores (notes, gamification, pomodoro, graph, settings, ...)
│   │   ├── components/   Reusable components (Modal, DynamicIcon, GoalCard, StreakListItem, ...)
│   │   ├── services/     Service modules (e.g. weatherService)
│   │   ├── actions/      Svelte actions (focusTrap, liquidGlass)
│   │   ├── utils/        Utilities (debug.ts logging gated by Dev Mode)
│   │   ├── api.ts        API client wrapper / push.ts — Web Push helper
│   └── app.html
├── static/               Static assets + PWA manifest
└── vite.config.ts        HMR config for Docker (clientPort 3000, host localhost)
```

### Icon Convention

- **Static icons**: import directly from `lucide-svelte` (tree-shakeable) —
  `import { Search, X } from 'lucide-svelte'`.
- **Dynamic icons** (name from data): `<DynamicIcon name={iconName} />` —
  runtime lookup, icon-pack switching (Lucide/Phosphor/Material).
- **Streak icons**: `<StreakIcon name={streak.icon} />` (emoji fallback).
  Never use `<DynamicIcon name="StaticName" />` with a hardcoded string.

## See Also

- [ARCHITECTURE.md](../ARCHITECTURE.md) / [ARCHITECTURE_FRONTEND.md](../ARCHITECTURE_FRONTEND.md)
- [AGENTS.md](../AGENTS.md) — agent instructions, commands, known issues
- [docs/](../docs/) — architecture decision records and guides
