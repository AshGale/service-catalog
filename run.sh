#!/usr/bin/env bash
# run.sh — start service-catalog locally
# Starts Postgres (if not already running) and the FastAPI server.
# Run setup.sh first if this is a fresh clone.

set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'
info() { echo -e "${CYAN}[run]${NC} $*"; }
ok()   { echo -e "${GREEN}[ok]${NC}  $*"; }
die()  { echo -e "${RED}[error]${NC} $*"; exit 1; }

echo ""
echo "=================================================="
echo "  service-catalog — starting"
echo "=================================================="
echo ""

# ── Preflight checks ───────────────────────────────────────────────────────
[[ -f .env ]] || die ".env not found. Run ./setup.sh first."
[[ -d .venv ]] || die ".venv not found. Run ./setup.sh first."
[[ -d frontend/dist ]] || die "frontend/dist not found. Run ./setup.sh first."

# ── Activate venv ──────────────────────────────────────────────────────────
if [[ -f .venv/Scripts/activate ]]; then
  source .venv/Scripts/activate
else
  source .venv/bin/activate
fi

# ── Start Postgres if not running ──────────────────────────────────────────
if docker compose ps 2>/dev/null | grep -q "catalog-db.*Up"; then
  ok "Postgres already running"
else
  info "Starting Postgres (Docker)..."
  docker compose up -d
  info "Waiting for Postgres to be ready..."
  until docker exec catalog-db pg_isready -U postgres -d catalog &>/dev/null; do
    sleep 1
  done
  ok "Postgres ready"
fi

echo ""
echo "  Dashboard → http://localhost:8000"
echo "  API docs  → http://localhost:8000/docs"
echo ""
echo "  Press Ctrl+C to stop."
echo ""

# ── Start the server ───────────────────────────────────────────────────────
uvicorn catalog_cli.server:app --reload --host 0.0.0.0 --port 8000
