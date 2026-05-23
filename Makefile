.PHONY: setup dev dev-d dev-reset prod stop restart logs build clean backup restore help migrate db-health test-api start doctor install-deps

COMPOSE_PROJECT ?= joidy
PLATFORM := $(shell uname -s | tr '[:upper:]' '[:lower:]')

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
	@echo ""
	@echo "Or use 'make start' for a guided setup + start!"
	@echo "────────────────────────────────────────────────────"

dev: ## Start all services in development mode (with hot reload)
	@if [ ! -f .env ]; then echo "Run 'make setup' first"; exit 1; fi
	@mkdir -p data/db data/uploads data/vault
	docker compose -p $(COMPOSE_PROJECT) -f docker-compose.yml -f docker-compose.dev.yml up --build

dev-d: ## Start all services in development mode (detached)
	@if [ ! -f .env ]; then echo "Run 'make setup' first"; exit 1; fi
	@mkdir -p data/db data/uploads data/vault
	docker compose -p $(COMPOSE_PROJECT) -f docker-compose.yml -f docker-compose.dev.yml up --build -d

dev-reset: ## Recreate all services in development mode from scratch (one command)
	@if [ ! -f .env ]; then echo "Run 'make setup' first"; exit 1; fi
	@mkdir -p data/db data/uploads data/vault
	docker compose -p $(COMPOSE_PROJECT) -f docker-compose.yml -f docker-compose.dev.yml down --remove-orphans --volumes
	docker compose -p $(COMPOSE_PROJECT) -f docker-compose.yml -f docker-compose.dev.yml up --build -d --force-recreate --remove-orphans --wait
	@echo "✓ Services recreated. Use 'make logs' to follow output."

prod: ## Start all services in production mode
	@if [ ! -f .env ]; then echo "Run 'make setup' first"; exit 1; fi
	@mkdir -p data/db data/uploads data/vault
	docker compose up --build -d

stop: ## Stop all services
	docker compose down

restart: ## Restart all services
	docker compose restart

logs: ## Tail logs from all services
	docker compose logs -f

logs-api: ## Tail API logs
	docker compose logs -f api

logs-ai: ## Tail AI service logs
	docker compose logs -f ai-service

logs-worker: ## Tail worker logs
	docker compose logs -f worker

build: ## Rebuild all Docker images
	docker compose build --no-cache

clean: ## Stop services and remove volumes (WARNING: deletes nothing in data/)
	docker compose down --remove-orphans

backup: ## Backup all user data to a timestamped archive
	@BACKUP_FILE="joidy-backup-$$(date +%Y-%m-%d_%H-%M-%S).tar.gz"; \
	tar -czf $$BACKUP_FILE data/; \
	echo "✓ Backup saved to $$BACKUP_FILE"

restore: ## Restore from a backup file: make restore FILE=joidy-backup-xxx.tar.gz
	@if [ -z "$(FILE)" ]; then echo "Usage: make restore FILE=joidy-backup-xxx.tar.gz"; exit 1; fi
	tar -xzf $(FILE)
	@echo "✓ Restored from $(FILE)"

shell-api: ## Open a shell in the api container
	docker compose exec api bash

shell-worker: ## Open a shell in the worker container
	docker compose exec worker bash

migrate: ## Run Alembic migrations up to head in api container
	docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm api sh -c "cd /app && alembic -c /app/alembic.ini upgrade head"

db-health: ## Verify migration head and required core tables
	docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm api sh -c "cd /app && alembic -c /app/alembic.ini current && python scripts/verify_db_health.py"

test-api: ## Run all API unit tests via unittest discover
	docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm api sh -c "PYTHONPATH=/app python -m unittest discover -s tests"

test-frontend: ## Run frontend typechecking (svelte-check) inside Docker
	docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm frontend npm run check

test: test-api test-frontend ## Run all test suites (API + Frontend)

lint-api: ## Check syntax of all Python services (api, ai-service, worker) inside Docker
	docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm api python -m compileall -q /app
	docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm ai-service python -m compileall -q /app
	docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm worker python -m compileall -q /app

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
	if ! command -v docker &> /dev/null; then \
		echo "$(RED)✗$(NC) Docker not found"; \
		EXIT_CODE=1; \
	else \
		echo "$(GREEN)✓$(NC) Docker: $$(docker --version | head -n1)"; \
	fi; \
	if ! (command -v docker compose &> /dev/null || docker compose version &> /dev/null); then \
		echo "$(RED)✗$(NC) Docker Compose not found"; \
		EXIT_CODE=1; \
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
	@source .env 2>/dev/null; \
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
	@if ! command -v docker &> /dev/null; then \
		echo "$(RED)Docker is not installed.$(NC)"; \
		echo ""; \
		echo "$(YELLOW)Please install Docker first:$(NC)"; \
		echo "  macOS:  https://docs.docker.com/desktop/install/mac-install/"; \
		echo "  Linux:  https://docs.docker.com/engine/install/"; \
		echo "  Windows: Use 'start.ps1' script instead"; \
		echo ""; \
		exit 1; \
	fi
	@if ! (command -v docker compose &> /dev/null || docker compose version &> /dev/null); then \
		echo "$(RED)Docker Compose is not available.$(NC)"; \
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
	@source .env 2>/dev/null; \
	if [ -z "$$GEMINI_API_KEY" ] || [ "$$GEMINI_API_KEY" = "your_gemini_api_key_here" ]; then \
		echo ""; \
		echo "$(YELLOW)⚠ GEMINI_API_KEY not set in .env$(NC)"; \
		echo "  Get your free key at: https://aistudio.google.com/"; \
		echo "  Then edit .env and add your key"; \
		echo ""; \
		echo "$(BLUE)Continue without AI features? (y/N)$(NC): "; \
		read -r CONTINUE; \
		if [ "$$CONTINUE" != "y" ] && [ "$$CONTINUE" != "Y" ]; then \
			echo "Aborted."; \
			exit 1; \
		fi; \
	fi
	@if [ -z "$$OBSIDIAN_VAULT_PATH" ] || [ "$$OBSIDIAN_VAULT_PATH" = "/path/to/your/obsidian/vault" ]; then \
		echo ""; \
		echo "$(YELLOW)⚠ OBSIDIAN_VAULT_PATH not set in .env$(NC)"; \
		echo "  Enter the absolute path to your Obsidian vault:"; \
		echo "  (e.g., /home/username/Documents/Obsidian)"; \
		echo ""; \
		echo "$(BLUE)Vault path (or press Enter to skip):$(NC) "; \
		read -r VAULT_PATH; \
		if [ -n "$$VAULT_PATH" ]; then \
			sed -i "s|^OBSIDIAN_VAULT_PATH=.*|OBSIDIAN_VAULT_PATH=$$VAULT_PATH|" .env; \
			echo "  ✓ Updated OBSIDIAN_VAULT_PATH in .env"; \
		fi; \
	fi
	@source .env 2>/dev/null; \
	if [ -z "$$SECRET_KEY" ] || [ "$$SECRET_KEY" = "change_this_to_a_random_secret_key" ]; then \
		NEW_SECRET=$$(openssl rand -hex 32 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || echo "dev_secret_$$(date +%s)"); \
		sed -i "s|^SECRET_KEY=.*|SECRET_KEY=$$NEW_SECRET|" .env; \
		echo "  ✓ Generated new SECRET_KEY"; \
	fi
	@echo ""
	@echo "Step 2: Starting services..."
	@docker compose -p $(COMPOSE_PROJECT) -f docker-compose.yml -f docker-compose.dev.yml up --build -d
	@echo ""
	@echo "── $(GREEN)Joidy is running!$(NC) ───────────────────────────────"
	@echo ""
	@echo "$(GREEN)  Web App:$(NC)   http://localhost:3000"
	@echo "$(GREEN)  API Docs:$(NC)  http://localhost:8000/docs"
	@echo ""
@echo "To view logs:  make logs"
	@echo "To stop:       make stop"
	@echo "────────────────────────────────────────────────────"

backup: ## Create a database backup
	@mkdir -p data/backups
	@docker compose exec -T api python /app/scripts/backup.py

restore: ## Restore from a backup file
	@echo "Available backups:"
	@ls -la data/backups/ 2>/dev/null || echo "No backups found"
	@echo ""
	@echo "Usage: cp data/backups/joidy_YYYYMMDD_HHMMSS.tar.gz /tmp/ && docker compose exec -T api sh -c 'cd /data && tar -xzf /tmp/joidy_*.tar.gz -C .'"

.PHONY: backup restore
