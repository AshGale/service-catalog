# catalog-cli — AI-First Service Catalog CLI (v1.0)

Deterministic + RAG-powered queries over Backstage catalog data, backed by PostgreSQL + pgvector and an internal Llama 3 endpoint.

## Quick start

```bash
# 1. Copy and edit the env file
cp .env.example .env

# 2. One command — starts Postgres, installs CLI, creates schema
make bootstrap

# 3. Done
catalog-cli --help
```

## Prerequisites

- Python 3.10+
- Docker / Docker Compose
- Access to the internal `/genai` endpoint (Llama 3)

## Makefile targets

```
make help          Show all targets
make up            Start the Postgres container (detached)
make down          Stop the Postgres container
make restart       Restart the Postgres container
make logs          Tail Postgres container logs
make status        Show container status and port
make psql          Open a psql shell against the catalog database
make install       Install the CLI in editable mode (with deps)
make install-web   Install with web UI dependencies (FastAPI + Uvicorn)
make init-db       Run the CLI's init-db command (idempotent)
make ingest        Ingest catalog-info.yaml files (set INGEST_PATH=./your/dir)
make serve         Start the web UI on port 8000
make bootstrap     Full first-time setup: container + install + init schema
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
| `CATALOG_GENAI_ENDPOINT` | `https://internal-api/genai` | Llama 3 /genai URL |
| `CATALOG_EMBEDDING_DIM` | `4096` | Embedding vector dimension |
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
```

### AI-powered queries (RAG)

```bash
catalog-cli ask "Which services publish to the kafka-payments-topic?"
catalog-cli ask "What would break if the Stripe API went down?" --top-k 10
catalog-cli ask "Summarise the payment service architecture" --no-stream
```

### Web UI

A browser-based dashboard for browsing services, viewing rendered Mermaid diagrams, running RAG queries, and drag-and-drop YAML ingestion.

```bash
# Install with web deps (if not already via bootstrap)
make install-web

# Start the server
make serve
# → http://localhost:8000
```

The API is also usable standalone (all endpoints under `/api/`).

## Project structure

```
catalog-cli/
├── catalog_cli/
│   ├── __init__.py     # Package version
│   ├── config.py       # Env-var config
│   ├── db.py           # Postgres queries + vector search
│   ├── genai.py        # /genai endpoint client (embed + generate)
│   ├── ingest.py       # YAML parser + upsert pipeline
│   ├── main.py         # Typer CLI entrypoint
│   └── server.py       # FastAPI web server
├── frontend/
│   └── dist/           # Built frontend assets (served by FastAPI)
├── db/
│   └── init.sql        # Schema applied on first container start
├── .env.example        # Config template
├── .gitignore
├── docker-compose.yml  # Postgres + pgvector container
├── Makefile            # Dev workflow shortcuts
├── pyproject.toml      # Python packaging
└── README.md
```
