# Changelog

<!-- hermes-release:pending v1.0.0 -->
## [v1.0.0] — 2026-10-08

### ⚠️ Breaking Changes

* chore(deps): Bump anthropic from 0.125.0 to 1.3.0 in /ai-service by @app/dependabot in https://github.com/Axel-DaMage/joidy/pull/906

### 🚀 Features

* feat(github): simplificar integracion con conexion por username y resolver error en Device Flow by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/979
* feat(streaks): permitir configurar rachas persistentes que nunca fallen en modo bola de nieve (#963) by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/978
* feat(ui): diferenciar colores de badges de tareas y rachas pendientes con contraste armónico dinámico (#968) by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/977
* feat(frontend): mostrar notas recientes si GitHub no está conectado y permitir alternar vistas (#970) by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/976
* feat(frontend): migrate Vite from v6 to v8 by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/944
* feat(agents): optimize repository structure and docs for agent-first development by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/943
* feat(goals): add archiving support, top-left action button, and hover-only card action buttons by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/941
* feat(goals): quick delete X button on goal cards with confirmation modal (#913) by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/940
* feat(settings): add direct creation links to GitHub PAT and OAuth settings (#937) by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/939
* feat(goals): record failed goal entry per uncompleted day for snowball goals by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/934
* feat(goals): prevent automatic failure on rollover goals and add manual fail button by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/929
* feat(goals): add quick complete and delete buttons to Editor tab goal cards by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/923
* feat(goals): add quick complete and delete buttons to GoalEditor by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/921
* feat(goals): default untimed goals to ONEOFF (Indefinido) state by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/919
* feat(integrations): configure GitHub token/keys from settings UI by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/903
* feat(goals): replace goal description with linked note by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/900
* feat(goals): reflect selected goal color on goal cards by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/899
* feat(goals): support one-off tasks in goals by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/898
* feat(cli): make 'joidy up' pull latest images automatically by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/897
* feat(ci): auto-publish AUR package on release by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/883
* feat(cli): port fallback for joidy up — try 5 subsequent ports before aborting by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/879

### 🐛 Bug Fixes

* fix(goals): redirigir al editor de objetivos tras crearlo (#984) by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/985
* fix(windows): resolve powershell script encoding, secrets generation and shims by @VECTORG99 in https://github.com/Axel-DaMage/joidy/pull/982
* fix(streaks): map frequency labels correctly with i18n support (#974) by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/975
* fix(focus): preservar el temporizador activo al entrar en modo enfoque (#967) by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/973
* fix(streaks): mejorar legibilidad y resplandor del estilo neon en rachas (#964) by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/972
* fix(goals): agregar estilos al botón de cerrar en modal de nuevo objetivo (#966) by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/971
* fix(goals): update syntax highlight immediately via rAF in GoalEditor (#936) by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/938
* fix(goals): prevent duplicate goals on note sync and compact card vertical space by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/927
* fix(goals): prevent duplicate goal creation when adding objective by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/918
* fix(goals): superpose completed state in week history & add editor quick actions by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/914
* fix(aur): normalize hyphens to underscores in pkgver by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/888
* fix(infra): run dev containers as host UID/GID so .svelte-kit never needs sudo by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/887
* fix(ci): use correct AUR_SSH_KEY secret name in aur-publish workflow by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/885
* fix(release): auto-bump pre-release series instead of spurious stable releases by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/884
* fix(cli): resolve_ports returns non-zero with set -e when no ports bumped by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/882
* fix(vault): expand ~ in OBSIDIAN_VAULT_PATH and add UI examples by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/880
* fix(ci): replace --notes-prepend with gh release edit by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/877

### ⚡ Performance

* perf(docker): optimize dockerfiles for multi-stage caching, security and size by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/942
* perf(db): propose database performance optimizations by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/902

### 🧹 Chores

* chore(deps): Bump pyjwt from 2.14.0 to 2.15.0 in /api in the pip group across 1 directory by @app/dependabot in https://github.com/Axel-DaMage/joidy/pull/1032
* chore(deps-dev): Bump eslint from 10.9.1 to 10.11.0 in /frontend by @app/dependabot in https://github.com/Axel-DaMage/joidy/pull/1031
* chore(deps): Bump marked from 18.0.11 to 18.0.14 in /frontend by @app/dependabot in https://github.com/Axel-DaMage/joidy/pull/1030
* chore(deps): Bump dompurify from 3.4.14 to 3.4.16 in /frontend by @app/dependabot in https://github.com/Axel-DaMage/joidy/pull/1029
* chore(deps-dev): Bump @types/node from 26.4.1 to 26.6.3 in /frontend by @app/dependabot in https://github.com/Axel-DaMage/joidy/pull/1028
* chore(deps): Bump the tiptap group in /frontend with 11 updates by @app/dependabot in https://github.com/Axel-DaMage/joidy/pull/1027
* chore(deps): Bump cryptography from 50.0.1 to 50.0.2 in /api by @app/dependabot in https://github.com/Axel-DaMage/joidy/pull/1026
* chore(deps): Bump cohere from 7.1.1 to 7.2.0 in /ai-service by @app/dependabot in https://github.com/Axel-DaMage/joidy/pull/1022
* chore(deps): Bump sqlalchemy from 2.0.54 to 2.1.1 in /worker by @app/dependabot in https://github.com/Axel-DaMage/joidy/pull/1020
* chore(deps): Bump uvicorn from 0.52.4 to 0.54.0 in /api by @app/dependabot in https://github.com/Axel-DaMage/joidy/pull/1018
* chore(deps): Bump openai from 3.11.0 to 3.22.1 in /ai-service by @app/dependabot in https://github.com/Axel-DaMage/joidy/pull/1017
* chore(deps): Bump devalue from 5.9.0 to 5.9.4 in /frontend by @app/dependabot in https://github.com/Axel-DaMage/joidy/pull/1015
* chore(deps-dev): Bump undici from 8.9.0 to 8.11.2 in /frontend by @app/dependabot in https://github.com/Axel-DaMage/joidy/pull/1014
* chore(deps): Bump pyjwt from 2.13.0 to 2.14.0 in /api in the pip group across 1 directory by @app/dependabot in https://github.com/Axel-DaMage/joidy/pull/1013
* chore(deps): Bump watchfiles from 1.2.0 to 1.3.0 in /worker by @app/dependabot in https://github.com/Axel-DaMage/joidy/pull/1011
* chore(deps): Bump alembic from 1.19.1 to 1.20.0 in /api by @app/dependabot in https://github.com/Axel-DaMage/joidy/pull/989
* chore(deps): Bump sqlalchemy from 2.0.52 to 2.1.1 in /api by @app/dependabot in https://github.com/Axel-DaMage/joidy/pull/988
* chore(deps): Bump sqlalchemy from 2.0.52 to 2.0.54 in /worker by @app/dependabot in https://github.com/Axel-DaMage/joidy/pull/987
* chore: release v1.1.0-beta.5 by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/986
* chore: release v1.1.0-beta.4 by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/980
* chore(deps): Bump numpy from 2.5.2 to 2.5.3 in /ai-service by @app/dependabot in https://github.com/Axel-DaMage/joidy/pull/962
* chore(deps): Bump openai from 3.5.0 to 3.11.0 in /ai-service by @app/dependabot in https://github.com/Axel-DaMage/joidy/pull/961
* chore(deps): Bump psycopg2-binary from 2.9.12 to 2.9.13 in /ai-service by @app/dependabot in https://github.com/Axel-DaMage/joidy/pull/960
* chore(deps): Bump psycopg2-binary from 2.9.12 to 2.9.13 in /api by @app/dependabot in https://github.com/Axel-DaMage/joidy/pull/959
* chore(deps): Bump psycopg2-binary from 2.9.12 to 2.9.13 in /worker by @app/dependabot in https://github.com/Axel-DaMage/joidy/pull/958
* chore(deps-dev): Bump svelte from 5.56.9 to 5.57.0 in /frontend by @app/dependabot in https://github.com/Axel-DaMage/joidy/pull/954
* chore(deps-dev): Bump @types/node from 26.4.0 to 26.4.1 in /frontend by @app/dependabot in https://github.com/Axel-DaMage/joidy/pull/953
* chore(deps-dev): Bump eslint from 10.8.0 to 10.9.1 in /frontend by @app/dependabot in https://github.com/Axel-DaMage/joidy/pull/952
* chore(deps-dev): Bump globals from 17.9.0 to 17.12.0 in /frontend by @app/dependabot in https://github.com/Axel-DaMage/joidy/pull/951
* chore(deps): Bump the tiptap group across 1 directory with 11 updates by @app/dependabot in https://github.com/Axel-DaMage/joidy/pull/950
* chore(deps): Bump pydantic from 2.13.4 to 2.13.5 in /ai-service by @app/dependabot in https://github.com/Axel-DaMage/joidy/pull/949
* chore(deps): Bump cohere from 7.1.0 to 7.1.1 in /ai-service by @app/dependabot in https://github.com/Axel-DaMage/joidy/pull/947
* chore(deps): Bump pywebpush from 2.4.0 to 2.5.0 in /api by @app/dependabot in https://github.com/Axel-DaMage/joidy/pull/946
* chore(deps): Bump pydantic from 2.13.4 to 2.13.5 in /api by @app/dependabot in https://github.com/Axel-DaMage/joidy/pull/945
* style(goals): make GoalCard action buttons permanently visible by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/925
* chore(deps-dev): Bump @types/node from 26.2.0 to 26.4.0 in /frontend by @app/dependabot in https://github.com/Axel-DaMage/joidy/pull/912
* chore(deps): Bump marked from 18.0.10 to 18.0.11 in /frontend by @app/dependabot in https://github.com/Axel-DaMage/joidy/pull/911
* chore(deps): Bump dompurify from 3.4.13 to 3.4.14 in /frontend by @app/dependabot in https://github.com/Axel-DaMage/joidy/pull/910
* chore(deps): Bump highlight.js from 11.11.1 to 11.12.0 in /frontend by @app/dependabot in https://github.com/Axel-DaMage/joidy/pull/909
* chore(deps): Bump the tiptap group across 1 directory with 11 updates by @app/dependabot in https://github.com/Axel-DaMage/joidy/pull/908
* chore(deps): Bump cohere from 7.0.9 to 7.1.0 in /ai-service by @app/dependabot in https://github.com/Axel-DaMage/joidy/pull/907
* chore(deps): Bump openai from 3.3.1 to 3.5.0 in /ai-service by @app/dependabot in https://github.com/Axel-DaMage/joidy/pull/905
* chore(deps): Bump cryptography from 50.0.0 to 50.0.1 in /api by @app/dependabot in https://github.com/Axel-DaMage/joidy/pull/904

### 📦 Other Changes

* [quality] 134 svelte-check warnings across 21 files + vitest localStorage env warnings — fix and enforce a warning budget by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/1005
* Release v1.1.0-beta.3 by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/956
* release: v1.1.0-beta.2 by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/955
* ui(goals): limit goal identity color selector to 8 colors by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/901
* release: merge development into main by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/889
* release: v1.0.0-beta.3 by @Axel-DaMage in https://github.com/Axel-DaMage/joidy/pull/881
<!-- /hermes-release:pending -->

All notable changes to Joidy are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Windows support & documentation**: Comprehensive troubleshooting guide for Windows (`docs/troubleshooting.md`), detailing PowerShell ExecutionPolicy, WSL 2 requirements for Docker Desktop, and Obsidian Vault path formatting (#981)
- **`joidy pull` command in `joidy.ps1`**: Added image pulling command to the Windows PowerShell CLI for parity with `joidy.sh` (#981)

### Changed

- **PowerShell CLI character encoding**: Replaced non-ASCII Unicode quotation-interfering characters (`✓`, `—`, `║`) with ASCII-safe escape sequences (`$([char]0x2713)`) in `joidy.ps1`, `install.ps1`, `install-autostart.ps1`, and `start.ps1` to prevent fatal syntax parser errors in Windows PowerShell 5.1 (#981)
- **`joidy.cmd` batch shim**: Updated shim to invoke PowerShell with `-NoProfile -ExecutionPolicy Bypass -File` to prevent opening Notepad when executed from `cmd.exe` (#981)
- **`.gitattributes`**: Added repository `.gitattributes` to enforce consistent CRLF for Windows scripts and LF for Unix scripts (#981)

### Fixed

- **Abstract class instantiation in `Generate-Secret`**: Fixed `New-Object Security.Cryptography.RandomNumberGenerator` throwing constructor error and generating all-zero secrets in `joidy.ps1`. Now uses `[System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)` (#981)
- **Undefined `Write-Ok` in `start.ps1`**: Added alias to `Write-Success` to avoid `CommandNotFoundException` during vault path expansion (#981)
- **Docker daemon readiness check**: Added pre-flight check for running Docker engine before attempting stack operations on Windows, providing clear error guidance instead of raw pipe socket errors (#981)

### Removed

- _Nothing yet_

### Security

- _Nothing yet_

## [1.0.0-beta.3] - 2026-08-24

### Added

- **Port fallback for `joidy up`** — if a service's host port is already bound by a foreign process, the CLI tries up to 5 subsequent ports before aborting (no half-started stack). Ports held by joidy's own compose project are reused, so re-running `joidy up` is idempotent (#879)

### Fixed

- **`~` not expanded in `OBSIDIAN_VAULT_PATH`** — Docker bind mounts do not expand `~`, so a vault path like `~/Documentos/notas/mi-vault` resolved to a broken relative path and the worker/api containers mounted the wrong directory. The CLI (`joidy.sh`, `joidy.ps1`, `start.ps1`) and Makefile targets now expand `~` to `$HOME` and export the absolute path for compose. The settings UI and Setup Wizard show examples and hints about `~` support (#880)

## [1.0.0-beta.2] - 2026-08-24

### Added

- **Podman rootless support** alongside Docker — CLI auto-detects engine, socket, and group; compose file and system router handle both label formats (`com.docker.compose.*` and `io.podman.compose.*`)
- **Logout button** in Settings panel with session display and i18n (EN/ES)
- **Service-to-service auth shortcut** — worker can authenticate with the bcrypt-hashed AUTH_PASSWORD stored in `.env` without knowing the plaintext

### Changed

- `AUTH_PASSWORD` and `SECRET_KEY` are now read from disk on every auth operation via `get_persisted()`, ensuring all Uvicorn workers see the same credentials immediately after setup without requiring a restart
- `POST /config/setup` no longer returns `requires_restart: true` — the cross-worker fix makes restart unnecessary
- `.env` updates via `write_env()` now preserve existing comments, blank lines, and commented-out template entries instead of rewriting the file as a flat key-value list
- `joidy.sh` CLI detects container engine (docker-compose → docker compose → podman compose → podman-compose) and auto-detects Docker socket group ID
- `docker-compose.yml` uses configurable `DOCKER_SOCK_PATH` and `DOCKER_GID` with engine-agnostic comments
- `.env.example` documents `DOCKER_SOCK_PATH` and `DOCKER_GID` for both Docker and Podman

### Fixed

- **`/config` HTTP 500** when `.env` bind mount is a directory — Docker creates a directory at `/app/.env` when the host-side bind source doesn't exist (system installs); `read_env()` now uses `Path.is_file()` instead of `exists()` (#876)
- **Cross-worker auth inconsistency** — Uvicorn `--workers 2` meant setup only updated the worker that served the request; siblings kept stale empty credentials; all workers now read from disk on every request
- **Worker 401 authentication failure** — `POST /config/setup` stores `AUTH_PASSWORD` as a bcrypt hash, but the worker sends that hash as the password to `/auth/login`; `verify_password()` now accepts the hash verbatim as a service-to-service shortcut
- **`.env` comments lost on update** — previous `write_env()` rewrote the file as a flat `KEY=VALUE` list, deleting all comments and commented-out template entries; new implementation updates active assignments in place and preserves the file layout

## [1.0.0-beta.1] - 2026-08-24

### Fixed

- **CLI auto-bootstrap .env on first run** — AUR/system installs no longer fail with missing `POSTGRES_PASSWORD`; `.env` is auto-created in `~/.config/joidy/.env` with generated secrets (#873, #874)

## [1.0.0-beta] - 2026-08-24

### Added

- Service power management UI in settings panel — hibernate, wake, and shutdown services from the web UI (#870, #871)
- Podman compatibility in start scripts and Makefile (#810)
- Infinite scroll for notes list (#809)
- Assigned GitHub PRs and issues in the status bar (#792, #805)
- Monthly calendar map and centered planning sort control (#783, #790, #804)
- Goal settings 3-lists-at-once with folded description into note (#788, #789, #803)
- GoalCard polish — borderless pin, state below title, square cards (#785, #786, #787, #801)
- Professional responsive design across all pages and components (#732)
- LAN IP display after `joidy up`/`restart`
- Doctor command to detect root-owned `.svelte-kit` before `make dev` (#781, #782)
- Auto-install joidy CLI into `~/.local/bin`
- PowerShell installer and `--profile ai` handling in CLI/autostart (#848, #850, #858)
- Self-hosted Geist fonts removing Google Fonts CDN dependency (#846, #859)
- Disable AI service in production + harden API for stable release (#845)
- Worker crash recovery with exponential backoff via supervisor (#818)
- Alembic migration serialization across uvicorn workers via `pg_advisory_lock` (#817)
- CI fork PR auto-approval policy documented (#811, #819)

### Fixed

- Streak timezone mismatch — counter showed 0 before check-in due to frontend/backend UTC offset (#864, #868)
- Check-in layout shift — smooth transitions added, share button repositioned to corner (#862, #863, #867)
- Progress track and module dots hardcoded to dark theme via `var(--border)` (#865, #866, #869)
- Theme-aware disconnect buttons and settings panel colors (#844, #857)
- Hardcoded dark colors in goals replaced with theme-aware CSS variables (#839, #842, #861)
- StreakHeatmap theme-aware empty cells + year view spacing (#840, #843, #855)
- Resize handle redesigned to be theme-aware and minimalist (#841, #856)
- Goal pin icon now shows only on hover (#838, #854)
- Google Calendar & Tasks hidden behind dev mode (#851, #853)

### Security

- AI service disabled in production by default (#845)
- API hardened for stable release — internal secret validation, reduced attack surface (#845)

### Changed

- Infra audit fixes — parameterized Docker images, multi-stage builds, cache mounts (#812)
- Dependabot updates: vitest, svelte, typescript-eslint, tiptap, uvicorn, openai, anthropic, cohere, pytest, sqlalchemy, and more

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

[unreleased]: https://github.com/Axel-DaMage/joidy/compare/v1.1.0-beta.3...HEAD
[1.0.0-beta.3]: https://github.com/Axel-DaMage/joidy/compare/v1.0.0-beta.2...v1.0.0-beta.3
[1.0.0-beta.2]: https://github.com/Axel-DaMage/joidy/compare/v1.0.0-beta.1...v1.0.0-beta.2
[1.0.0-beta.1]: https://github.com/Axel-DaMage/joidy/compare/v1.0.0-beta...v1.0.0-beta.1
[1.0.0-beta]: https://github.com/Axel-DaMage/joidy/compare/v0.2.0...v1.0.0-beta
[0.2.0]: https://github.com/Axel-DaMage/joidy/releases/tag/v0.2.0
[0.1.0]: https://github.com/Axel-DaMage/joidy/releases/tag/v0.1.0
