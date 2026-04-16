SHELL := /bin/bash

UV := uv
PY := $(UV) run python
COMPOSE := docker compose
APP_MODULE := app.main:app
APP_HOST ?= 0.0.0.0
APP_PORT ?= 8000
MIGRATION_MSG ?=

.DEFAULT_GOAL := help

.PHONY: help check-env install sync run run-dev \
	up down restart build rebuild ps logs logs-app logs-db \
	db-up db-down db-reset \
	health shell-app shell-db \
	migrate migrate-down migrate-reset migrate-current migrate-history migrate-heads \
	migrate-revision migrate-autorevision \
	migrate-docker migrate-down-docker migrate-current-docker \
	deploy

help: ## Show available commands
	@echo "Arcana Bot commands:"
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z0-9_.-]+:.*##/ {printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

check-env: ## Ensure .env exists
	@test -f .env || (echo ".env file not found. Create it before running commands." && exit 1)

install: check-env ## Install dependencies and create venv
	$(UV) sync

sync: install ## Alias for install

run: check-env ## Run API/bot locally
	$(UV) run uvicorn $(APP_MODULE) --host $(APP_HOST) --port $(APP_PORT)

run-dev: check-env ## Run API/bot locally with reload
	$(UV) run uvicorn $(APP_MODULE) --reload --host $(APP_HOST) --port $(APP_PORT)

build: check-env ## Build docker images
	$(COMPOSE) build

up: check-env ## Start full stack in Docker (db + app)
	$(COMPOSE) up -d

down: ## Stop and remove containers
	$(COMPOSE) down

restart: down up ## Restart full Docker stack

rebuild: check-env ## Rebuild and restart full stack
	$(COMPOSE) up -d --build

ps: ## Show running compose services
	$(COMPOSE) ps

logs: ## Tail logs for all services
	$(COMPOSE) logs -f --tail=200

logs-app: ## Tail logs for app service
	$(COMPOSE) logs -f --tail=200 app

logs-db: ## Tail logs for db service
	$(COMPOSE) logs -f --tail=200 db

db-up: check-env ## Start only PostgreSQL service
	$(COMPOSE) up -d db

db-down: ## Stop only PostgreSQL service
	$(COMPOSE) stop db

db-reset: ## Recreate database volume (destructive)
	$(COMPOSE) down -v

health: ## Check HTTP health endpoint
	curl -fsS "http://localhost:$(APP_PORT)/health" || (echo "Health check failed" && exit 1)

shell-app: ## Open shell in app container
	$(COMPOSE) exec app bash

shell-db: ## Open psql shell in db container
	$(COMPOSE) exec db psql -U $$DB_USER -d $$DB_NAME

migrate: check-env ## Apply latest Alembic migrations locally
	$(UV) run alembic upgrade head

migrate-down: check-env ## Rollback one Alembic migration locally
	$(UV) run alembic downgrade -1

migrate-reset: check-env ## Rollback all migrations locally
	$(UV) run alembic downgrade base

migrate-current: check-env ## Show current local Alembic revision
	$(UV) run alembic current

migrate-history: check-env ## Show local Alembic migration history
	$(UV) run alembic history

migrate-heads: check-env ## Show Alembic heads
	$(UV) run alembic heads

migrate-revision: check-env ## Create empty Alembic migration: make migrate-revision MIGRATION_MSG="name"
	@if [ -z "$(MIGRATION_MSG)" ]; then \
		echo 'MIGRATION_MSG is required. Example: make migrate-revision MIGRATION_MSG="add users table"'; \
		exit 1; \
	fi
	$(UV) run alembic revision -m "$(MIGRATION_MSG)"

migrate-autorevision: check-env ## Create autogen migration: make migrate-autorevision MIGRATION_MSG="name"
	@if [ -z "$(MIGRATION_MSG)" ]; then \
		echo 'MIGRATION_MSG is required. Example: make migrate-autorevision MIGRATION_MSG="add readings indexes"'; \
		exit 1; \
	fi
	$(UV) run alembic revision --autogenerate -m "$(MIGRATION_MSG)"

migrate-docker: check-env ## Apply migrations inside app container
	$(COMPOSE) exec app uv run alembic upgrade head

migrate-down-docker: check-env ## Rollback one migration inside app container
	$(COMPOSE) exec app uv run alembic downgrade -1

migrate-current-docker: check-env ## Show current migration in app container
	$(COMPOSE) exec app uv run alembic current

deploy: check-env ## Build, start stack and apply migrations
	$(COMPOSE) up -d --build
	$(COMPOSE) exec app uv run alembic upgrade head
	@echo "Deploy completed."
