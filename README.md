<p align="center">
  <a href="https://joidy-web.vercel.app/">
    <img src="https://img.shields.io/badge/JOIDY-v1.0.0--alpha-8B5CF6?style=for-the-badge" alt="Joidy">
  </a>
</p>

<p align="center">
  <a href="https://joidy-web.vercel.app/">
    <img src="https://img.shields.io/badge/Web_App-Vercel-000000?style=for-the-badge&logo=vercel" alt="Web App">
  </a>
  <a href="https://github.com/Axel-DaMage/joidy/actions/workflows/ci.yml">
    <img src="https://img.shields.io/github/actions/workflow/status/Axel-DaMage/joidy/ci.yml?style=for-the-badge&logo=github" alt="CI">
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/License-GPL_v3-181717?style=for-the-badge" alt="License">
  </a>
  <a href="https://github.com/Axel-DaMage/joidy/releases">
    <img src="https://img.shields.io/github/v/release/Axel-DaMage/joidy?style=for-the-badge&logo=docker" alt="Release">
  </a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/SvelteKit-5-FF3E00?style=for-the-badge&logo=svelte" alt="SvelteKit">
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/PostgreSQL-16-4169E1?style=for-the-badge&logo=postgresql" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker" alt="Docker">
</p>

Personal knowledge management system with gamification. Manage notes, goals, streaks, and skills through a web dashboard with AI-powered features.

Try it live at **[joidy-web.vercel.app](https://joidy-web.vercel.app/)**.

---

## Installation

### Docker Hub (recommended)

```bash
docker pull d4mag3/joidy-api:latest
docker pull d4mag3/joidy-frontend:latest
docker pull d4mag3/joidy-ai-service:latest
docker pull d4mag3/joidy-worker:latest
```

Or clone and run locally:

```bash
git clone https://github.com/Axel-DaMage/joidy.git
cd joidy
cp .env.example .env
# Edit .env with your credentials
docker compose up -d
```

### Quick Start

| Platform | Command |
|----------|---------|
| Linux / macOS | `make start` |
| Windows | `powershell -ExecutionPolicy Bypass -File start.ps1` |

`make start` creates required directories, configures `.env` interactively, and launches all services.

Verify setup: `make doctor` (Linux/macOS) or `.\start.ps1 -Check` (Windows).

---

## Requirements

- Docker + Docker Compose

---

## Configuration

Edit `.env` after running setup:

| Variable | Description | Source |
|----------|-------------|--------|
| `GEMINI_API_KEY` | AI service key | [Google AI Studio](https://aistudio.google.com/app/apikey) |
| `OBSIDIAN_VAULT_PATH` | Path to your Obsidian vault | e.g. `/home/user/Documents/Obsidian` |
| `SECRET_KEY` | Session signing key | Auto-generated on first setup |

Optional:

```env
GITHUB_TOKEN=          # GitHub sync
GITHUB_USERNAME=
TELEGRAM_BOT_TOKEN=    # Notifications
TELEGRAM_ALLOWED_USER_ID=
```

---

## Usage

### Services

| Service | URL |
|---------|-----|
| Web App | http://localhost:3000 |
| API Docs | http://localhost:8000/docs |
| AI Service | http://localhost:8002 |

### Commands (Linux/macOS)

| Command | Description |
|---------|-------------|
| `make dev` | Start services with hot reload |
| `make stop` | Stop all services |
| `make logs` | View logs in real time |
| `make dev-reset` | Full reset (remove volumes, recreate) |
| `make test` | Run all tests |
| `make migrate` | Run database migrations |

### Commands (Windows)

Use `docker compose up -d` / `docker compose down`.

---

## Architecture

```
.
├── api/              FastAPI REST backend
├── ai-service/       AI service (Gemini, OpenAI, etc.)
├── worker/           Background tasks (Obsidian sync, daily summaries)
├── frontend/         SvelteKit web application
├── data/             Database, uploads, vault
├── docker-compose.yml
└── Makefile
```

---

## Integrations

| Service | Status |
|---------|--------|
| Gemini AI | Active (ai-service) |
| GitHub | Active (sync, issues, PRs) |
| Obsidian | Active (vault sync) |
| Gmail | Planned |
| Google Calendar | Planned |
| Strava | Planned |
| Spotify | Planned |

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Docker not found | Install Docker Desktop and ensure it is running |
| Port conflict | Override ports in `.env`: `FRONTEND_PORT=3001`, `API_PORT=8001` |
| Database not starting | Run `make migrate` |
| Service health | `make db-health` |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Look for issues labeled [`good-first-issue`](https://github.com/Axel-DaMage/joidy/issues?q=is%3Aissue+is%3Aopen+label%3Agood-first-issue) to get started.

---

## License

GNU General Public License v3.0. See [LICENSE](LICENSE).

---

Created by [D4MAG3_WIZ4RD](https://github.com/d4mag3). Contributors welcome.
