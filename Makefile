.PHONY: help up down restart logs psql install install-web install-dev init-db ingest serve test lint clean nuke status

# Load .env if present (won't fail if missing)
-include .env
export

# ── Defaults ────────────────────────────────────────────────────────────
CATALOG_DB_USER   ?= postgres
CATALOG_DB_NAME   ?= catalog
CATALOG_DB_PORT   ?= 5432
INGEST_PATH       ?= ./services

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

# ── Docker ──────────────────────────────────────────────────────────────

up: ## Start the Postgres container (detached)
	docker compose up -d

down: ## Stop the Postgres container
	docker compose down

restart: ## Restart the Postgres container
	docker compose restart

logs: ## Tail Postgres container logs
	docker compose logs -f db

status: ## Show container status and port
	@docker compose ps

psql: ## Open a psql shell against the catalog database
	docker exec -it catalog-db psql -U $(CATALOG_DB_USER) -d $(CATALOG_DB_NAME)

# ── CLI ─────────────────────────────────────────────────────────────────

install: ## Install the CLI in editable mode (with deps)
	pip install -e .

init-db: ## Run the CLI's init-db command (idempotent)
	catalog-cli init-db

ingest: ## Ingest catalog-info.yaml files (set INGEST_PATH=./your/dir)
	catalog-cli ingest $(INGEST_PATH)

# ── Web UI ─────────────────────────────────────────────────────────────

install-web: ## Install with web UI dependencies (FastAPI + Uvicorn)
	pip install -e ".[web]"

install-ui: ## Install frontend npm dependencies
	cd frontend && npm install

build-ui: ## Build the React/TS frontend into frontend/dist/
	cd frontend && npm run build

dev-ui: ## Start Vite dev server (hot reload, proxies /api to port 8000)
	cd frontend && npm run dev

serve: ## Start the FastAPI server on port 8000 (serves built frontend + API)
	uvicorn catalog_cli.server:app --reload --host 0.0.0.0 --port 8000

# ── Testing & Quality ──────────────────────────────────────────────────

install-dev: ## Install everything (CLI + web + test + lint)
	pip install -e ".[dev]"

test: ## Run tests (no DB required — everything is mocked)
	pytest tests/ -v

lint: ## Lint and format with Ruff
	ruff check catalog_cli/ tests/
	ruff format --check catalog_cli/ tests/

fmt: ## Auto-format with Ruff
	ruff check --fix catalog_cli/ tests/
	ruff format catalog_cli/ tests/

# ── Setup shortcut ──────────────────────────────────────────────────────

bootstrap: up ## Full first-time setup: container + install + init schema + build UI
	@echo "Waiting for Postgres to be healthy…"
	@until docker exec catalog-db pg_isready -U $(CATALOG_DB_USER) -d $(CATALOG_DB_NAME) > /dev/null 2>&1; do sleep 1; done
	@echo "Postgres ready."
	$(MAKE) install-web
	$(MAKE) init-db
	$(MAKE) install-ui
	$(MAKE) build-ui
	@echo "\n✓ Ready. Run: make serve  or  catalog-cli --help"

# ── Cleanup ─────────────────────────────────────────────────────────────

clean: down ## Stop container and remove the volume (wipes all data)
	docker compose down -v

nuke: clean ## Full nuke: container, volume, and pip uninstall
	pip uninstall -y catalog-cli 2>/dev/null || true
