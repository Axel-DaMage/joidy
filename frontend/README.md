# Frontend Service

SvelteKit web application for Joidy — the user-facing dashboard for notes,
goals, streaks, skills, the knowledge graph, and AI features. Runs on
**port 3000**.

## Tech Stack

- **SvelteKit** + **Vite** + **TypeScript**
- Svelte 5 runes (`$state`, `$derived`, `$effect`)
- CSS variables for theming
- PWA support
- `lucide-svelte` icons, `vitest` for unit tests

## Prerequisites

- Docker + Docker Compose (recommended), or Node.js 20+ with `npm`
- The `api` service reachable at the URL in `VITE_API_URL`
- `.env` configured from `.env.example` (`VITE_API_URL=http://localhost:8000`)

## Development

Start the full stack with hot reload from the repo root:

```bash
make dev          # all services, hot reload (Ctrl+C to stop)
make logs         # view logs (filter with make logs-frontend if available)
```

To run the frontend standalone:

```bash
cd frontend
npm install
npm run dev       # Vite dev server on http://localhost:3000
```

Or via Docker:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up frontend
```

## Environment Variables

- `VITE_API_URL` — base URL of the API service (see
  [`.env.example`](.env.example))
- `FRONTEND_PORT` — override the default 3000 (set in the root `.env`)

See root [`.env.example`](../.env.example) for service-wide variables.

## Testing

```bash
cd frontend
npm run check     # svelte-check type checking
npm run lint      # eslint
npm run test      # vitest unit tests
```

End-to-end tests (from repo root):

```bash
make test-frontend   # npx playwright test
```

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
│   │   ├── api.ts        API client wrapper
│   │   └── push.ts       Web Push subscription helper
│   └── app.html
├── static/               Static assets + PWA manifest
├── svelte.config.js
├── vite.config.ts        HMR config for Docker (clientPort 3000, host localhost)
└── package.json
```

### Icon Convention

- **Static icons** (always the same, e.g. close/search): import directly from
  `lucide-svelte` — `import { Search, X } from 'lucide-svelte'` (tree-shakeable).
- **Dynamic icons** (name from data/config): use
  `<DynamicIcon name={iconName} />` for runtime lookup with icon-pack
  switching (Lucide/Phosphor/Material).
- **Streak icons**: use `<StreakIcon name={streak.icon} />` (emoji fallback).
- Never use `<DynamicIcon name="StaticName" />` with a hardcoded string.

Dev Mode is stored in localStorage key `joidy-dev-mode` (toggled in Settings);
pages under development show "En Construccion" unless Dev Mode is ON.

## See Also

- [Architecture](../docs/architecture.md) — system overview and data flow
- [Frontend](../docs/frontend.md) — frontend architecture
- [AGENTS.md](../AGENTS.md) — agent instructions, commands, known issues
- [docs/](../docs/) — architecture decision records and guides
