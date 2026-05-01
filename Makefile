.PHONY: setup dev dev-d dev-reset prod stop restart logs build clean backup restore help migrate db-health test-api

COMPOSE_PROJECT ?= joidy

# ─────────────────────────────────────────────────
# Joidy Makefile
# Usage: make <command>
# ─────────────────────────────────────────────────

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

setup: ## First-time setup: copy .env, create data directories
	@echo "── Joidy Setup ──────────────────────────────"
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "✓ Created .env from .env.example"; \
		echo "  → Edit .env and add your GEMINI_API_KEY"; \
		echo "  → Set OBSIDIAN_VAULT_PATH to your vault folder"; \
	else \
		echo "✓ .env already exists"; \
	fi
	@mkdir -p data/db data/uploads data/vault
	@echo "✓ Created data directories"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Edit .env with your API keys"
	@echo "  2. Run: make dev"
	@echo "─────────────────────────────────────────────"

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

test-api: ## Run API unit tests for remediation scenarios
	docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm api sh -c "PYTHONPATH=/app python -m unittest tests.test_embedding_retry tests.test_gamification_config tests.test_tag_graph_service"
