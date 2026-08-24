# Changelog

All notable changes to Joidy are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- _Nothing yet_

### Changed

- _Nothing yet_

### Fixed

- _Nothing yet_

### Removed

- _Nothing yet_

### Security

- _Nothing yet_

## [1.0.0-beta] - 2026-08-24

### Added

- **Service power management UI** in settings panel — hibernate, wake, and shutdown services from the web UI (#870, #871)
- **Podman compatibility** in start scripts and Makefile (#810)
- **Infinite scroll** for notes list (#809)
- **Assigned GitHub PRs and issues** in the status bar (#792, #805)
- **Monthly calendar map** and centered planning sort control (#783, #790, #804)
- **Goal settings 3-lists-at-once** with folded description into note (#788, #789, #803)
- **GoalCard polish** — borderless pin, state below title, square cards (#785, #786, #787, #801)
- **Professional responsive design** across all pages and components (#732)
- **LAN IP display** after `joidy up`/`restart`
- **Doctor command** to detect root-owned `.svelte-kit` before `make dev` (#781, #782)
- **Auto-install joidy CLI** into `~/.local/bin`
- **PowerShell installer** and `--profile ai` handling in CLI/autostart (#848, #850, #858)
- **Self-hosted Geist fonts** removing Google Fonts CDN dependency (#846, #859)
- **Disable AI service in production** + harden API for stable release (#845)
- **Worker crash recovery** with exponential backoff via supervisor (#818)
- **Alembic migration serialization** across uvicorn workers via `pg_advisory_lock` (#817)
- **CI fork PR auto-approval** policy documented (#811, #819)

### Changed

- **Infra audit fixes** — parameterized Docker images, multi-stage builds, cache mounts, security gaps (#812)
- **Goal description** removed as separate field, folded into note editor (#789)
- **Sidebar nav order** swapped streaks and goals (#773)
- **Version strings** aligned to 0.2.0 with automated future bumps (#754)
- **Docs consolidated** — removed duplicated content and legacy ADR (#755, #758)
- **Dependabot updates**: vitest 4.1.11, @vitest/coverage-v8 4.1.11, typescript-eslint 8.67.0, svelte 5.56.9, @tiptap/* 3.30.2, uvicorn 0.52.4, openai 3.3.1, anthropic 0.125.0, cohere 7.0.9, pytest 9.1.1, sqlalchemy 2.0.52, pydantic-settings 2.15.0, alembic 1.19.1, aiofiles 25.1.0, pywebpush 2.4.0, aiodocker 0.27.0, marked 18.0.10, @sveltejs/kit 2.70.3, svelte-check 4.7.6

### Fixed

- **Streak timezone mismatch** — counter showed 0 before check-in due to frontend/backend UTC offset (#864, #868)
- **Check-in layout shift** — smooth transitions added, share button repositioned to corner (#862, #863, #867)
- **Progress track and module dots** hardcoded to dark theme via `var(--border)` (#865, #866, #869)
- **Theme-aware disconnect buttons** and settings panel colors (#844, #857)
- **Hardcoded dark colors in goals** replaced with theme-aware CSS variables (#839, #842, #861)
- **StreakHeatmap** theme-aware empty cells + year view spacing (#840, #843, #855)
- **Resize handle** redesigned to be theme-aware and minimalist (#841, #856)
- **Goal pin icon** now shows only on hover (#838, #854)
- **Google Calendar & Tasks** hidden behind dev mode (#851, #853)
- **Note delete confirmation** modal + empty-state one-page (#791, #795, #802)
- **LiquidGlass action** applied to streak Glass theme preview (#784, #800)
- **Toast icon color** for dark-mode contrast (#793, #798)
- **Broken icons** and non-reactive dashboard carousel (#783)
- **Production image** permission-safe and self-contained
- **Vite HMR** uses IPv4 to fix Docker networking
- **Vault path change** warns user when container recreation is needed (#784)
- **make db-health** repaired and stray version strings aligned
- **Playwright config** and stale E2E selectors (#776, #777)
- **Goal creation modal** columns balanced, internal scroll fixed (#764)
- **Goals page** tabs and editor overflow on mobile
- **Notes folder creation** and empty vault folders visible in tree
- **Power management** runtime bugs found during testing

### Security

- **AI service disabled in production** by default (#845)
- **API hardened** for stable release — internal secret validation, reduced attack surface (#845)

## [0.2.0] - 2026-08-16

### Added

- **Security hardening**: JWT auth enforced on all data/mutation endpoints, API keys/secrets exposure fixed, XSS & input sanitization, CORS & WebSocket auth, ai-service hardening, all containers run as non-root user (#322, #323, #324, #325, #326, #327, #329, #358, #376, #377, #378, #379, #380, #397, #408, #416, #417, #418, #419, #422, #423)
- **Google Calendar & Tasks OAuth integration** (#2, #374)
- **WYSIWYG markdown editor** with TipTap (#6, #344)
- **Real-time sync conflict detection and resolution** (#5, #321)
- **Obsidian bidirectional sync via webhook** (#3, #320)
- **ModalDialog component** replacing inline modals in goals page (#319)
- **Image and file attachments** in notes (#67, #182)
- **Distributed tracing and structured logging** (#38)
- **Dead Letter Queue UI** for failed embeddings
- **Undo/redo history** in note editor
- **Graph minimap, zoom in/out, and search improvements**
- **Dashboard widgets reorderable** via drag & drop
- **Bulk operations on notes** (select multiple, delete/tag/untag)
- **Weekly activity progress bar** on dashboard
- **Search filter and level filter** to skills page
- **Markdown formatting toolbar** to note editor
- **Autosave in note editor** with debounce and crash recovery
- **Scientific calculator** extracted from notes page
- **Unified Integrations page**, fix GitHub OAuth, remove dead routes
- **Onboarding interface** for first run (#106)
- **Backend endpoints for initial setup** (#106)
- **Command palette** (Cmd+K) (#63)
- **Folder creation and deletion** (#47)
- **PWA beforeinstallprompt handling** (#72)
- **Visual indicators to sidebar** for page status (#51)
- **ErrorBoundary component** and global error handlers (#65)
- **Notes file tree reorganization** via context menu
- **Focus trapping and ARIA attributes** to Modal component
- **Weather caching** in WeatherWidget (#50)
- **Multi-platform publish** (npm, brew, AUR, curl) + README with all links
- **Production docker-compose** consuming DockerHub images
- **Workflow to publish images to DockerHub** on release
- **QUICKSTART.md** and mermaid architecture diagram to README (#29, #183)
- **ARCHITECTURE_FRONTEND.md** with frontend stores, components and data flow (#181)
- **Release and versioning process** (`RELEASE.md`, `CHANGELOG.md`, `release.yml`)
- **ESLint + Prettier** configuration for frontend (#346)
- **Pre-commit hooks** for frontend (svelte-check, eslint, prettier) (#337)
- **Docker healthchecks** for ai-service and worker (#335)
- **pip cache** in CI and **coverage artifact** upload (#330)
- **Responsive media queries** to 8 pages for mobile (#405)
- **aria-label** to all icon-only buttons for accessibility (#396)
- **WeatherWidget fetch** extracted to weatherService with caching (#348)
- **Configurable log levels** in production via localStorage (#395)
- **localStorage SSR guards** using `browser` from `$app/environment` (#404)

### Changed

- **Database migrated from SQLite to PostgreSQL 16 + pgvector** in all environments (#273)
- **DI/repository pattern** implemented, removed legacy UnitOfWork (#37)
- **docker-compose.yml** restructured as production, dev compose with builds
- **DynamicIcon** replaces direct lucide-svelte imports for dynamic icons (#74)
- **GoalCard** extracted from goals page into dedicated component
- **StreakListItem** extracted from streaks page into dedicated component
- **Goals chart** simplified — replaced candlestick with bar chart
- **lint-api** now runs via Docker instead of host Python (#334)
- **sed -i** in Makefile made portable for macOS (#334)
- **AUR PKGBUILD** dependency changed from docker-compose to docker plugin (#331)
- **ADRs updated** to reflect PostgreSQL + pgvector migration (#338)
- **Logger** refactored to allow configurable log levels in production (#395)

### Fixed

- **High-priority bugs batch** (#359, #360, #361, #368)
- **6 medium-priority issues** (#273, #252, #274, #270, #271, #266)
- **5 high-priority issues** (#269, #268, #265, #261, #260)
- **DynamicIcon prop name** and note source_path type
- **Streaks hover-only buttons** now visible on mobile/touch devices
- **Onboarding 500 error** by removing invalid vault_path setting
- **Service Worker** no longer intercepts Vite Dev dependencies
- **svelte-check strict typing errors** to unblock CI
- **Worker authentication** and volume mounts for local development
- **Type errors** in folder API logic
- **Real user data fetched after login** instead of hardcoding (#61)
- **CI pipeline** fixed for SQLite tests and Docker builds (#20)
- **CI health check** no longer silenced with `|| true` (#330)
- **localStorage access** without browser check causing SSR errors (#404)
- **Logger silencing all logs** in production including errors (#395)
- **WeatherWidget direct API call** bypassing centralized api.ts (#348)

### Removed

- **npm/bun publishing** (joidy-cli package)
- **6 dead .svelte components** never imported (#385)
- **4 unused icon packages** from devDependencies (#382)
- **Unused Python dependencies** (aiofiles, gitpython) (#383)
- **TODO.md**, the last stray file in repo root (#332)
- **Deprecated files** from repo root

### Security

- **All containers run as non-root user** (#329)
- **API keys & secrets exposure** fixed (#358, #377, #380)
- **XSS & input sanitization** added (#376, #397, #366)
- **CORS & WebSocket auth** hardened (#326, #325, #378)
- **ai-service hardening** with internal secret validation
- **Auth & security hardening** across all endpoints (#322, #323, #324, #327, #379, #408)
- **Explicit permissions** added to all CI jobs (#330)

## [0.1.0] - 2026-07-30

### Added

- Initial project scaffolding: FastAPI backend, SvelteKit frontend, AI service, worker, Docker Compose setup.
- Note CRUD with Markdown, WikiLink parsing, tags, and AI embeddings.
- Gamification engine: XP, streaks, plant growth stages.
- Goals with temporal types and rollover/snowball failure modes.
- Skill tree auto-generation from tag usage.
- Tag co-occurrence knowledge graph.
- Obsidian vault sync and bidirectional import.
- GitHub OAuth device flow integration.
- Image and file attachments in notes.
- Responsive base layout and mobile streak actions.
- CI pipeline: API tests, frontend typecheck, Docker build smoke test.

[unreleased]: https://github.com/Axel-DaMage/joidy/compare/v1.0.0-beta...HEAD
[1.0.0-beta]: https://github.com/Axel-DaMage/joidy/compare/v0.2.0...v1.0.0-beta
[0.2.0]: https://github.com/Axel-DaMage/joidy/releases/tag/v0.2.0
[0.1.0]: https://github.com/Axel-DaMage/joidy/releases/tag/v0.1.0
