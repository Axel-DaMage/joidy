.PHONY: setup dev dev-d dev-reset prod stop restart logs logs-api logs-ai logs-worker build clean backup restore shell-api shell-worker migrate db-health test-api test-frontend test-frontend-e2e test lint lint-api fix-permissions install-deps doctor start

COMPOSE_PROJECT ?= joidy
DOCKER_COMPOSE := $(shell command -v docker-compose >/dev/null 2>&1 && echo "docker-compose" || (command -v docker >/dev/null 2>&1 && echo "docker compose" || (command -v podman-compose >/dev/null 2>&1 && echo "podman-compose" || (command -v podman >/dev/null 2>&1 && echo "podman compose" || echo "docker compose"))))
PLATFORM := $(shell uname -s | tr '[:upper:]' '[:lower:]')
# Portable sed in-place: GNU sed uses -i, BSD sed (macOS) needs -i ''
SED_INPLACE := $(shell sed --version >/dev/null 2>&1 && echo "sed -i" || echo "sed -i ''")

RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[0;33m
BLUE := \033[0;34m
NC := \033[0m

# ─────────────────────────────────────────────────
# Joidy Makefile
# Usage: make <command>
# ─────────────────────────────────────────────────

help: ## Show this help
	@echo ""
	@echo "$(BLUE)Joidy - Personal Knowledge Management System$(NC)"
	@echo ""
	@echo "$(YELLOW)Quick Start (Linux/Mac):$(NC)"
	@echo "  make start            🚀 Setup + start all services (interactive)"
	@echo "  make doctor           Verify prerequisites"
	@echo "  make install-deps     Check Docker installation"
	@echo ""
	@echo "$(YELLOW)Basic Commands:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'
	@echo ""
	@echo "$(YELLOW)Windows Users:$(NC)"
	@echo "  Use start.ps1 instead of make start"
	@echo "  Run: powershell -ExecutionPolicy Bypass -File start.ps1"
	@echo "────────────────────────────────────────────────────"

setup: ## First-time setup: copy .env, create data directories
	@echo ""
	@echo "── $(BLUE)Joidy Setup$(NC) ────────────────────────────────"
	@mkdir -p data/db data/uploads data/vault
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "$(GREEN)✓$(NC) Created .env from .env.example"; \
		echo ""; \
		echo "$(YELLOW)Next steps:$(NC)"; \
		echo "  1. Edit .env with your API keys"; \
		echo "     - GEMINI_API_KEY: get free at https://aistudio.google.com/"; \
		echo "     - OBSIDIAN_VAULT_PATH: absolute path to your vault"; \
		echo "  2. Run: make dev"; \
	else \
		echo "$(GREEN)✓$(NC) .env already exists"; \
		echo "  Run 'make doctor' to check your configuration"; \
	fi
	@. .env 2>/dev/null || true; \
	if [ -z "$$POSTGRES_PASSWORD" ]; then \
		NEW_PW=$$(openssl rand -hex 24 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(24))" 2>/dev/null || echo "dev_pw_$$(date +%s)"); \
		$(SED_INPLACE) "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$$NEW_PW|" .env; \
		echo "$(GREEN)✓$(NC) Generated POSTGRES_PASSWORD"; \
	fi
	@echo ""
	@echo "Or use 'make start' for a guided setup + start!"
	@echo "────────────────────────────────────────────────────"

dev: ## Start all services in development mode (with hot reload)
	@if [ ! -f .env ]; then echo "Run 'make setup' first"; exit 1; fi
	@mkdir -p data/db data/uploads data/vault
	$(DOCKER_COMPOSE) -p $(COMPOSE_PROJECT) -f docker-compose.yml -f docker-compose.dev.yml --profile ai up --build

dev-d: ## Start all services in development mode (detached)
	@if [ ! -f .env ]; then echo "Run 'make setup' first"; exit 1; fi
	@mkdir -p data/db data/uploads data/vault
	$(DOCKER_COMPOSE) -p $(COMPOSE_PROJECT) -f docker-compose.yml -f docker-compose.dev.yml --profile ai up --build -d

dev-reset: ## Recreate all services in development mode from scratch (one command)
	@if [ ! -f .env ]; then echo "Run 'make setup' first"; exit 1; fi
	@mkdir -p data/db data/uploads data/vault
	$(DOCKER_COMPOSE) -p $(COMPOSE_PROJECT) -f docker-compose.yml -f docker-compose.dev.yml --profile ai down --remove-orphans --volumes
	$(DOCKER_COMPOSE) -p $(COMPOSE_PROJECT) -f docker-compose.yml -f docker-compose.dev.yml --profile ai up --build -d --force-recreate --remove-orphans --wait
	@echo "✓ Services recreated. Use 'make logs' to follow output."

prod: ## Start all services in production mode
	@if [ ! -f .env ]; then echo "Run 'make setup' first"; exit 1; fi
	@mkdir -p data/db data/uploads data/vault
	$(DOCKER_COMPOSE) up --build -d

stop: ## Stop all services
	$(DOCKER_COMPOSE) down

restart: ## Restart all services
	$(DOCKER_COMPOSE) restart

logs: ## Tail logs from all services
	$(DOCKER_COMPOSE) logs -f

logs-api: ## Tail API logs
	$(DOCKER_COMPOSE) logs -f api

logs-ai: ## Tail AI service logs
	$(DOCKER_COMPOSE) logs -f ai-service

logs-worker: ## Tail worker logs
	$(DOCKER_COMPOSE) logs -f worker

build: ## Rebuild all Docker images
	$(DOCKER_COMPOSE) build --no-cache

clean: ## Stop services and remove volumes, __pycache__ and MCP logs (WARNING: deletes nothing in data/)
	$(DOCKER_COMPOSE) down --remove-orphans
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name .playwright-mcp -prune -exec rm -rf {} +
	find . -type f -name '*.py[co]' -delete

backup: ## Backup all user data to a timestamped archive
	@BACKUP_FILE="joidy-backup-$$(date +%Y-%m-%d_%H-%M-%S).tar.gz"; \
	tar -czf $$BACKUP_FILE data/; \
	echo "✓ Backup saved to $$BACKUP_FILE"

restore: ## Restore from a backup file: make restore FILE=joidy-backup-xxx.tar.gz
	@if [ -z "$(FILE)" ]; then echo "Usage: make restore FILE=joidy-backup-xxx.tar.gz"; exit 1; fi
	tar -xzf $(FILE)
	@echo "✓ Restored from $(FILE)"

shell-api: ## Open a shell in the api container
	$(DOCKER_COMPOSE) exec api bash

shell-worker: ## Open a shell in the worker container
	$(DOCKER_COMPOSE) exec worker bash

migrate: ## Run Alembic migrations up to head in api container
	$(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml run --rm api sh -c "cd /app && alembic -c /app/alembic.ini upgrade head"

db-health: ## Verify migration head and required core tables
	$(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml run --rm api sh -c "cd /app && alembic -c /app/alembic.ini current && PYTHONPATH=/app python scripts/verify_db_health.py"

test-api: ## Run all API unit tests via pytest
	$(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml run --rm api sh -c "cd /app && pytest --cov --cov-report=term-missing"

test-frontend: ## Run frontend unit tests (vitest) inside Docker
	$(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml run --rm frontend npm run test:run

test-frontend-e2e: ## Run frontend E2E tests (Playwright) — requires running stack
	$(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml run --rm frontend npx playwright test

test-frontend-check: ## Run frontend typechecking (svelte-check) inside Docker
	$(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml run --rm frontend npm run check

test: test-api test-frontend test-frontend-check ## Run all test suites (API + Frontend + typecheck)

lint-api: ## Check syntax of all Python services via Docker (compileall)
	$(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml run --rm api python -m compileall -q /app/api /app/ai-service /app/worker || (echo "Syntax errors found"; exit 1)

lint: lint-api ## Run all linters and code checkers

fix-permissions: ## Fix project permissions (run once with sudo make fix-permissions)
	sudo bash scripts/fix-permissions.sh

# ─────────────────────────────────────────────────
# Quick Start Commands (Linux/Mac)
# ─────────────────────────────────────────────────

install-deps: ## Check and show Docker installation instructions
	@echo ""
	@echo "── $(BLUE)Checking Docker...$(NC) ────────────────────────────"
	@if command -v docker &> /dev/null; then \
		echo "$(GREEN)✓$(NC) Docker is installed"; \
		docker --version; \
	else \
		echo "$(RED)✗$(NC) Docker is not installed"; \
		echo ""; \
		echo "$(YELLOW)Install Docker:$(NC)"; \
		echo "  macOS:  https://docs.docker.com/desktop/install/mac-install/"; \
		echo "  Linux:  https://docs.docker.com/engine/install/"; \
		echo "  Windows: https://docs.docker.com/desktop/install/windows-install/"; \
	fi
	@echo ""
	@if command -v docker compose &> /dev/null; then \
		echo "$(GREEN)✓$(NC) Docker Compose is available"; \
	elif docker compose version &> /dev/null; then \
		echo "$(GREEN)✓$(NC) Docker Compose (plugin) is available"; \
	else \
		echo "$(RED)✗$(NC) Docker Compose is not available"; \
	fi
	@echo ""

doctor: ## Verify all prerequisites are met
	@echo "── $(BLUE)Joidy Doctor$(NC) ────────────────────────────────────"
	@echo ""
	@echo "Checking prerequisites..."
	@echo ""
	@EXIT_CODE=0; \
	if command -v docker &> /dev/null; then \
		echo "$(GREEN)✓$(NC) Docker: $$(docker --version | head -n1)"; \
		if command -v docker-compose &> /dev/null || docker compose version &> /dev/null; then \
			echo "$(GREEN)✓$(NC) Docker Compose: available"; \
		else \
			echo "$(RED)✗$(NC) Docker Compose not found"; \
			EXIT_CODE=1; \
		fi; \
	elif command -v podman &> /dev/null; then \
		echo "$(GREEN)✓$(NC) Podman: $$(podman --version | head -n1)"; \
		if command -v podman-compose &> /dev/null || podman compose version &> /dev/null; then \
			echo "$(GREEN)✓$(NC) Podman Compose: available"; \
		else \
			echo "$(RED)✗$(NC) Podman Compose not found"; \
			EXIT_CODE=1; \
		fi; \
	else \
		echo "$(RED)✗$(NC) Neither Docker nor Podman found"; \
		EXIT_CODE=1; \
	fi; \
	if ! command -v make &> /dev/null; then \
		echo "$(RED)✗$(NC) make not found"; \
		EXIT_CODE=1; \
	else \
		echo "$(GREEN)✓$(NC) make found"; \
	fi; \
	if ! command -v python3 &> /dev/null; then \
		echo "$(YELLOW)⚠$(NC) python3 not found (optional, but recommended)"; \
	else \
		echo "$(GREEN)✓$(NC) python3 found"; \
	fi; \
	if ! command -v npm &> /dev/null; then \
		echo "$(YELLOW)⚠$(NC) npm not found (optional, but recommended for frontend)"; \
	else \
		echo "$(GREEN)✓$(NC) npm found"; \
	fi; \
	echo ""; \
	if [ ! -f .env ]; then \
		echo "$(YELLOW)⚠$(NC) .env file not found"; \
		echo "  Run: make setup"; \
		EXIT_CODE=1; \
	else \
		echo "$(GREEN)✓$(NC) .env exists"; \
	fi; \
	echo ""; \
	. .env 2>/dev/null || true; \
	if [ -z "$$GEMINI_API_KEY" ] || [ "$$GEMINI_API_KEY" = "your_gemini_api_key_here" ]; then \
		echo "$(YELLOW)⚠$(NC) GEMINI_API_KEY not configured"; \
		echo "  Get free key at: https://aistudio.google.com/"; \
		EXIT_CODE=1; \
	else \
		echo "$(GREEN)✓$(NC) GEMINI_API_KEY configured"; \
	fi; \
	if [ -z "$$OBSIDIAN_VAULT_PATH" ] || [ "$$OBSIDIAN_VAULT_PATH" = "/path/to/your/obsidian/vault" ]; then \
		echo "$(YELLOW)⚠$(NC) OBSIDIAN_VAULT_PATH not configured"; \
		EXIT_CODE=1; \
	else \
		echo "$(GREEN)✓$(NC) OBSIDIAN_VAULT_PATH: $$OBSIDIAN_VAULT_PATH"; \
		if [ -d "$$OBSIDIAN_VAULT_PATH" ]; then \
			echo "$(GREEN)  ✓ Vault directory exists$(NC)"; \
		else \
			echo "$(YELLOW)  ⚠ Vault directory does not exist yet$(NC)"; \
		fi; \
	fi; \
	echo ""; \
	if [ -d "./data/db" ]; then \
		echo "$(GREEN)✓$(NC) data/db directory exists"; \
	else \
		echo "$(YELLOW)⚠$(NC) data/db directory not found"; \
	fi; \
	echo ""; \
	if [ -d "frontend/.svelte-kit" ]; then \
		if [ -e "frontend/.svelte-kit/env.d.ts" ] && [ ! -w "frontend/.svelte-kit/env.d.ts" ]; then \
			echo "$(YELLOW)⚠$(NC) frontend/.svelte-kit/env.d.ts is not writable (likely root-owned)"; \
			echo "  The frontend dev container (uid 1000) will crash on start with EACCES"; \
			echo "  Run: sudo make fix-permissions"; \
			EXIT_CODE=1; \
		elif [ ! -w "frontend/.svelte-kit" ]; then \
			echo "$(YELLOW)⚠$(NC) frontend/.svelte-kit is not writable (likely root-owned)"; \
			echo "  The frontend dev container (uid 1000) will crash on start with EACCES"; \
			echo "  Run: sudo make fix-permissions"; \
			EXIT_CODE=1; \
		else \
			echo "$(GREEN)✓$(NC) frontend/.svelte-kit is writable"; \
		fi; \
	else \
		echo "$(GREEN)✓$(NC) frontend/.svelte-kit will be generated on first start"; \
	fi; \
	echo ""; \
	if [ $$EXIT_CODE -eq 0 ]; then \
		echo "$(GREEN)All checks passed! Run 'make dev' to start.$(NC)"; \
	else \
		echo "$(YELLOW)Please fix the issues above before starting.$(NC)"; \
	fi; \
	exit $$EXIT_CODE

start: ## 🚀 Quick start: setup + start all services
	@echo ""
	@echo "── $(BLUE)Joidy Quick Start$(NC) ────────────────────────────────"
	@echo ""
	@if ! command -v docker &> /dev/null && ! command -v podman &> /dev/null; then \
		echo "$(RED)Neither Docker nor Podman is installed.$(NC)"; \
		echo ""; \
		echo "$(YELLOW)Please install Docker or Podman first:$(NC)"; \
		echo "  Docker:  https://docs.docker.com/engine/install/"; \
		echo "  Podman:  https://podman.io/docs/installation"; \
		echo ""; \
		exit 1; \
	fi
	@if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null && ! command -v podman-compose &> /dev/null && ! podman compose version &> /dev/null; then \
		echo "$(RED)Container Compose tool is not available.$(NC)"; \
		exit 1; \
	fi
	@echo "Step 1: Setting up environment..."
	@mkdir -p data/db data/uploads data/vault
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "  ✓ Created .env from .env.example"; \
	fi
	@if [ ! -f .env ]; then \
		echo "$(RED)Failed to create .env$(NC)"; \
		exit 1; \
	fi
	@. .env 2>/dev/null || true; \
	if [ -z "$$GEMINI_API_KEY" ] || [ "$$GEMINI_API_KEY" = "your_gemini_api_key_here" ]; then \
		echo ""; \
		echo "$(YELLOW)⚠ GEMINI_API_KEY not set in .env$(NC)"; \
		echo "  Get your free key at: https://aistudio.google.com/"; \
		echo "  Then edit .env and add your key"; \
		echo ""; \
		echo -n "$(BLUE)Continue without AI features? (y/N)$(NC): "; \
		read -r CONTINUE; \
		if [ "$$CONTINUE" != "y" ] && [ "$$CONTINUE" != "Y" ]; then \
			echo "Aborted."; \
			exit 1; \
		fi; \
	fi
	@. .env 2>/dev/null || true; \
	if [ -z "$$OBSIDIAN_VAULT_PATH" ] || [ "$$OBSIDIAN_VAULT_PATH" = "/path/to/your/obsidian/vault" ]; then \
		echo ""; \
		echo "$(YELLOW)⚠ OBSIDIAN_VAULT_PATH not set in .env$(NC)"; \
		echo "  Enter the absolute path to your Obsidian vault:"; \
		echo "  (e.g., /home/username/Documents/Obsidian)"; \
		echo ""; \
		echo -n "$(BLUE)Vault path (or press Enter to skip):$(NC) "; \
		read -r VAULT_PATH; \
		if [ -n "$$VAULT_PATH" ]; then \
			$(SED_INPLACE) "s|^OBSIDIAN_VAULT_PATH=.*|OBSIDIAN_VAULT_PATH=$$VAULT_PATH|" .env; \
			echo "  ✓ Updated OBSIDIAN_VAULT_PATH in .env"; \
		fi; \
	fi
	@. .env 2>/dev/null || true; \
	if [ -z "$$SECRET_KEY" ] || [ "$$SECRET_KEY" = "change_this_to_a_random_secret_key" ]; then \
		NEW_SECRET=$$(openssl rand -hex 32 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || echo "dev_secret_$$(date +%s)"); \
		$(SED_INPLACE) "s|^SECRET_KEY=.*|SECRET_KEY=$$NEW_SECRET|" .env; \
		echo "  ✓ Generated new SECRET_KEY"; \
	fi
	@. .env 2>/dev/null || true; \
	if [ -z "$$POSTGRES_PASSWORD" ]; then \
		NEW_PW=$$(openssl rand -hex 24 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(24))" 2>/dev/null || echo "dev_pw_$$(date +%s)"); \
		$(SED_INPLACE) "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$$NEW_PW|" .env; \
		echo "  ✓ Generated new POSTGRES_PASSWORD"; \
	fi
	@echo ""
	@echo "Step 2: Starting services..."
	@$(DOCKER_COMPOSE) -p $(COMPOSE_PROJECT) -f docker-compose.yml -f docker-compose.dev.yml up --build -d
	@echo ""
	@echo "── $(GREEN)Joidy is running!$(NC) ───────────────────────────────"
	@echo ""
	@echo "$(GREEN)  Web App:$(NC)   http://localhost:3000"
	@echo "$(GREEN)  API Docs:$(NC)  http://localhost:8000/docs"
	@echo ""
	@echo "To view logs:  make logs"
	@echo "To stop:       make stop"
	@echo "────────────────────────────────────────────────────"
