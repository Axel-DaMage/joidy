<p align="center">
  <img src="https://img.shields.io/badge/JOIDY-v1.0.0--alpha-8B5CF6?style=for-the-badge" alt="Joidy">
</p>

<p align="center">
  <a href="https://github.com/Axel-DaMage/joidy/actions/workflows/ci.yml">
    <img src="https://img.shields.io/github/actions/workflow/status/Axel-DaMage/joidy/ci.yml?style=for-the-badge&logo=github" alt="CI">
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/License-GPL_v3-181717?style=for-the-badge" alt="License">
  </a>
  <a href="https://github.com/Axel-DaMage/joidy/releases">
    <img src="https://img.shields.io/github/v/release/Axel-DaMage/joidy?style=for-the-badge" alt="Release">
  </a>
</p>

<p align="center">
  <a href="https://joidy-web.vercel.app/">Web App</a>
  &middot;
  <a href="#docker">Docker</a>
  &middot;
  <a href="#curl">curl</a>
  &middot;
  <a href="#npm--bun">npm / bun</a>
  &middot;
  <a href="#homebrew">Homebrew</a>
  &middot;
  <a href="#aur">AUR</a>
</p>

Personal knowledge management system with gamification. Manage notes, goals, streaks, and skills through a web dashboard with AI-powered features.

---

## Installation

### Docker

```bash
git clone https://github.com/Axel-DaMage/joidy.git
cd joidy
cp .env.example .env
docker compose up -d
```

### curl

```bash
curl -fsSL https://raw.githubusercontent.com/Axel-DaMage/joidy/main/scripts/install.sh | bash
```

### npm / bun

```bash
npx @joidy-app/cli up
# or
bunx @joidy-app/cli up
```

### Homebrew

```bash
brew tap Axel-DaMage/homebrew-tap
brew install joidy
joidy up
```

### AUR

```bash
yay -S joidy
# or
paru -S joidy
```

---

## Requirements

- Docker + Docker Compose

---

## Configuration

Edit `.env` after cloning:

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

| Service | URL |
|---------|-----|
| Web App | http://localhost:3000 |
| API Docs | http://localhost:8000/docs |

### Development

```bash
make dev       # Hot reload, source mounts
make stop      # Stop all services
make logs      # View logs
make test      # Run tests
make migrate   # Database migrations
```

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

## License

GNU General Public License v3.0. See [LICENSE](LICENSE).
