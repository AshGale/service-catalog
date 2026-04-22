# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# First-time setup (Docker + install + DB schema)
make bootstrap

# Development install
make install-dev       # CLI + web + test + lint deps

# Run tests (no DB required — mocked)
make test
pytest tests/test_specific.py::test_name   # single test

# Lint and format
make lint              # ruff check + format validation
make fmt               # auto-format with ruff

# Database
make up                # start PostgreSQL container
make init-db           # create schema (idempotent)
make psql              # open psql shell

# Ingest and serve
make ingest INGEST_PATH=./path/to/yamls
make serve             # uvicorn on port 8000 with reload
```

**Ruff config:** Python 3.10+, line length 100, double quotes, rules E/F/I/UP/B/SIM (E501 ignored).

## Architecture

This is an AI-first service catalog CLI/API built on Backstage `catalog-info.yaml` data. It has two query modes:

- **Deterministic** (zero tokens): `get`, `list`, `tags`, `deps`, `diagram` — direct PostgreSQL queries
- **RAG-powered** (tokens): `ask` — embed question → vector search → LLM context → answer

### Data flow

**Ingestion:** `catalog-info.yaml` → `ingest.py:parse_catalog_yaml()` → `genai.py:embed()` → `db.py:upsert_service()`

**Deterministic query:** CLI/API → `db.py` → structured metadata

**RAG query:** question → `genai.py:embed()` → `db.py:vector_search()` (pgvector cosine similarity) → top-K YAML chunks → `genai.py:generate()` → answer

### Module responsibilities

| Module | Role |
|---|---|
| `catalog_cli/config.py` | Env var loading (DB, genai endpoint, embedding dims) |
| `catalog_cli/db.py` | All PostgreSQL access — deterministic queries + vector search + upsert |
| `catalog_cli/genai.py` | Internal `/genai` endpoint client — `embed()`, `generate()`, `generate_stream()` |
| `catalog_cli/ingest.py` | YAML parsing + embedding pipeline |
| `catalog_cli/main.py` | Typer CLI entry point (`catalog-cli` command) |
| `catalog_cli/server.py` | FastAPI web server, serves `/api/*` and static frontend from `frontend/dist/` |

### Database schema

Single table `service_catalog` with: `id` (UUID), `service_name` (UNIQUE), `owner`, `lifecycle`, `metadata` (JSONB — tags, dependencies, APIs), `raw_content` (TEXT), `embedding` (VECTOR[4096]), `last_updated`. HNSW index on `embedding`. Schema applied via `init.sql` on first container start; `catalog-cli init-db` applies it manually (idempotent).

### Configuration

Copy `.env.example` to `.env`. Key vars: `CATALOG_DB_*` (host/port/name/user/password), `CATALOG_GENAI_URL` (internal Llama 3 endpoint), `CATALOG_EMBEDDING_DIM` (default 4096), `CATALOG_RAG_TOP_K` (default 5).

### Entry points

- CLI: `catalog-cli` (pyproject.toml → `catalog_cli.main:app`)
- Web: `uvicorn catalog_cli.server:app --reload --host 0.0.0.0 --port 8000` (or `make serve`)
- Docker: `docker-compose.yml` runs `pgvector/pgvector:pg16`
