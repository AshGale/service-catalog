# catalog-cli — AI-First Service Catalog CLI (v1.0)

Deterministic + RAG-powered queries over Backstage catalog data, backed by PostgreSQL + pgvector and an Ollama backend (nomic-embed-text + llama3.1:8b). Includes a React/TypeScript dashboard served by FastAPI.

## Getting started

Two scripts, that's it.

**Step 1 — run once after cloning:**

```bash
./setup.sh
```

Checks that Python 3.10+, Node 18+, and Docker are installed, creates a virtual environment, installs all dependencies, starts Postgres, initialises the database schema, builds the frontend, and pulls the Ollama models.

**Step 2 — every time you want to run the app:**

```bash
./run.sh
```

Starts Postgres (if not already running) and the FastAPI server. Open **http://localhost:8000**.

> **Windows users:** run both scripts in Git Bash (comes with Git for Windows). If you don't have Git Bash, use `make bootstrap` / `make serve` instead (see below).

## Prerequisites

The setup script will tell you if anything is missing, but you'll need:

- [Python 3.10+](https://python.org)
- [Node.js 18+](https://nodejs.org) (includes npm)
- [Docker Desktop](https://docs.docker.com/get-docker/)
- [Ollama](https://ollama.com/download) — for AI-powered `ask` queries (optional, rest of the app works without it)

## Quick start (make / manual)

### With make

```bash
# 1. Copy and edit the env file
cp .env.example .env

# 2. One command — starts Postgres, installs CLI + frontend, creates schema, builds UI
make bootstrap

# 3. Start the server
make serve
# → http://localhost:8000
```

### Without make

```bash
# 1. Copy and edit the env file
copy .env.example .env

# 2. Start Postgres
docker compose up -d

# 3. Install the Python CLI and web deps
pip install -e ".[web]"

# 4. Create the database schema
catalog-cli init-db

# 5. Install and build the frontend
cd frontend && npm install && npm run build && cd ..

# 6. Start the server
uvicorn catalog_cli.server:app --reload --host 0.0.0.0 --port 8000
# → http://localhost:8000
```

## Makefile targets

```
make help          Show all targets

# Database
make up            Start the Postgres container (detached)
make down          Stop the Postgres container
make restart       Restart the Postgres container
make logs          Tail Postgres container logs
make status        Show container status and port
make psql          Open a psql shell against the catalog database

# Python
make install       Install the CLI in editable mode (with deps)
make install-web   Install with web server dependencies (FastAPI + Uvicorn)
make install-dev   Install everything (CLI + web + test + lint)
make init-db       Create the database schema (idempotent)
make ingest        Ingest catalog-info.yaml files (set INGEST_PATH=./your/dir)

# Frontend
make install-ui    Install frontend npm dependencies
make build-ui      Build the React/TS frontend into frontend/dist/
make dev-ui        Start Vite dev server with hot reload (proxies /api to port 8000)

# Server
make serve         Start FastAPI on port 8000 (serves built frontend + API)

# Setup shortcut
make bootstrap     Full first-time setup: Postgres + CLI + schema + frontend build

# Cleanup
make clean         Stop container and remove the volume (wipes all data)
make nuke          Full nuke: container, volume, and pip uninstall
```

## Configuration

All config is via environment variables (or `.env` file). See `.env.example` for defaults.

| Variable | Default | Description |
|---|---|---|
| `CATALOG_DB_HOST` | `localhost` | Postgres host |
| `CATALOG_DB_PORT` | `5432` | Postgres port |
| `CATALOG_DB_NAME` | `catalog` | Database name |
| `CATALOG_DB_USER` | `postgres` | Database user |
| `CATALOG_DB_PASSWORD` | `changeme` | Database password |
| `CATALOG_GENAI_URL` | `http://localhost:11434` | Ollama base URL |
| `CATALOG_EMBEDDING_DIM` | `768` | Embedding vector dimension (nomic-embed-text) |
| `CATALOG_RAG_TOP_K` | `5` | Default context docs for `ask` |

## Usage

### Ingest services

```bash
# Single file
catalog-cli ingest ./services/payment-service/catalog-info.yaml

# Recursively walk a directory
catalog-cli ingest ./services/

# Via Makefile (uses INGEST_PATH, defaults to ./services)
make ingest
make ingest INGEST_PATH=./my-repos
```

### Deterministic queries (zero tokens)

```bash
catalog-cli get payment-processing-service
catalog-cli tags payment-processing-service
catalog-cli diagram payment-processing-service
catalog-cli list
catalog-cli list --owner team-finance --lifecycle production
catalog-cli list --tag critical-path
catalog-cli deps payment-processing-service
catalog-cli dump              # export full catalog as JSON
catalog-cli dump --format yaml
```

### AI-powered queries (RAG)

```bash
catalog-cli ask "Which services publish to the kafka-payments-topic?"
catalog-cli ask "What would break if the Stripe API went down?" --top-k 10
catalog-cli ask "Summarise the payment service architecture" --no-stream
```

### Web UI

The dashboard runs on the same port as the API. It has three views:

- **Catalog** — browse services, filter by name/owner, view tags, metadata, Mermaid diagrams, and dependencies
- **Ask** — RAG-powered natural language queries with conversation history
- **Ingest** — drag-and-drop `catalog-info.yaml` upload

#### Option A — Production mode (single port)

Build the frontend once, then FastAPI serves everything from port 8000.

```bash
# With make
make build-ui
make serve

# Without make
cd frontend && npm run build && cd ..
uvicorn catalog_cli.server:app --reload --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000`

#### Option B — Dev mode (hot reload)

Run FastAPI and the Vite dev server side by side. Vite proxies `/api` calls to FastAPI automatically.

```bash
# Terminal 1 — FastAPI backend
# With make
make serve

# Without make
uvicorn catalog_cli.server:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 — Vite frontend (hot reload)
# With make
make dev-ui

# Without make
cd frontend && npm run dev
```

Open `http://localhost:5173`

## Project structure

```
catalog-cli/
├── catalog_cli/
│   ├── __init__.py         Package version
│   ├── config.py           Env-var config
│   ├── db.py               Postgres queries + pgvector search
│   ├── genai.py            Ollama client (embed + generate)
│   ├── ingest.py           YAML parser + upsert pipeline
│   ├── main.py             Typer CLI entrypoint
│   └── server.py           FastAPI server (API + static frontend)
├── frontend/
│   ├── src/
│   │   ├── App.tsx         React/TypeScript dashboard (single-file)
│   │   ├── main.tsx        React entry point
│   │   └── vite-env.d.ts   Vite type shims
│   ├── dist/               Built assets served by FastAPI (git-ignored)
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts      Dev proxy + build config
│   ├── tsconfig.json
│   ├── tsconfig.app.json
│   └── tsconfig.node.json
├── services/               Example catalog-info.yaml files
├── db/
│   └── init.sql            Schema applied on first container start
├── docs/
│   └── rag-pipeline.md     RAG architecture walkthrough
├── .env.example            Config template
├── docker-compose.yml      Postgres + pgvector container
├── Makefile                Dev workflow shortcuts
├── pyproject.toml          Python packaging
└── README.md
```
