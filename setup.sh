#!/usr/bin/env bash
# setup.sh — one-shot setup for service-catalog
# Works on macOS, Linux, and Windows Git Bash.
# Run once after cloning. Then use run.sh to start the app.

set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[setup]${NC} $*"; }
ok()      { echo -e "${GREEN}[ok]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[warn]${NC}  $*"; }
die()     { echo -e "${RED}[error]${NC} $*"; exit 1; }

echo ""
echo "=================================================="
echo "  service-catalog — first-time setup"
echo "=================================================="
echo ""

# ── 1. Check required tools ────────────────────────────────────────────────
info "Checking required tools..."

command -v python3 &>/dev/null || command -v python &>/dev/null \
  || die "Python 3.10+ is required. Install from https://python.org"

PYTHON=$(command -v python3 2>/dev/null || command -v python)
PY_VER=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$($PYTHON -c "import sys; print(sys.version_info.major)")
PY_MINOR=$($PYTHON -c "import sys; print(sys.version_info.minor)")
[[ $PY_MAJOR -gt 3 || ($PY_MAJOR -eq 3 && $PY_MINOR -ge 10) ]] \
  || die "Python 3.10+ required, found $PY_VER"
ok "Python $PY_VER"

command -v node &>/dev/null || die "Node.js 18+ is required. Install from https://nodejs.org"
NODE_VER=$(node --version | tr -d 'v' | cut -d. -f1)
[[ $NODE_VER -ge 18 ]] || die "Node.js 18+ required, found $(node --version)"
ok "Node.js $(node --version)"

command -v npm &>/dev/null || die "npm is required (comes with Node.js)"
ok "npm $(npm --version)"

command -v docker &>/dev/null || die "Docker is required. Install from https://docs.docker.com/get-docker/"
docker info &>/dev/null || die "Docker daemon is not running. Start Docker and try again."
ok "Docker $(docker --version | awk '{print $3}' | tr -d ',')"

# Ollama — soft check, warn but don't fail (can be added later)
if command -v ollama &>/dev/null; then
  ok "Ollama found"
  HAVE_OLLAMA=true
else
  warn "Ollama not found — AI (RAG) queries won't work until it's installed."
  warn "  Install: https://ollama.com/download"
  HAVE_OLLAMA=false
fi

echo ""

# ── 2. Copy .env ────────────────────────────────────────────────────────────
info "Configuring environment..."
if [[ ! -f .env ]]; then
  cp .env.example .env
  ok "Created .env from .env.example (defaults are fine for local dev)"
else
  ok ".env already exists — skipping"
fi

echo ""

# ── 3. Python virtual environment ──────────────────────────────────────────
info "Setting up Python virtual environment..."
if [[ ! -d .venv ]]; then
  $PYTHON -m venv .venv
  ok "Created .venv"
else
  ok ".venv already exists — skipping"
fi

# Activate venv (cross-platform: Git Bash uses Scripts/, Unix uses bin/)
if [[ -f .venv/Scripts/activate ]]; then
  source .venv/Scripts/activate
else
  source .venv/bin/activate
fi
ok "Activated .venv"

# ── 4. Install Python deps ─────────────────────────────────────────────────
info "Installing Python dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -e ".[web]"
ok "Python packages installed"

echo ""

# ── 5. Start Postgres ──────────────────────────────────────────────────────
info "Starting Postgres (Docker)..."
docker compose up -d

info "Waiting for Postgres to be ready..."
until docker exec catalog-db pg_isready -U postgres -d catalog &>/dev/null; do
  sleep 1
done
ok "Postgres is ready"

echo ""

# ── 6. Initialise database schema ──────────────────────────────────────────
info "Creating database schema..."
catalog-cli init-db
ok "Schema created (idempotent — safe to re-run)"

echo ""

# ── 7. Frontend ────────────────────────────────────────────────────────────
info "Installing frontend dependencies..."
cd frontend
npm install --silent
ok "npm packages installed"

info "Building frontend..."
npm run build --silent
cd ..
ok "Frontend built → frontend/dist/"

echo ""

# ── 8. Ollama models ───────────────────────────────────────────────────────
if [[ $HAVE_OLLAMA == true ]]; then
  info "Pulling Ollama models (this may take a few minutes on first run)..."
  ollama pull nomic-embed-text && ok "nomic-embed-text ready"
  ollama pull llama3.1:8b     && ok "llama3.1:8b ready"
  echo ""
fi

# ── Done ───────────────────────────────────────────────────────────────────
echo "=================================================="
echo -e "${GREEN}  Setup complete!${NC}"
echo "=================================================="
echo ""
echo "  Start the app any time with:"
echo ""
echo "    ./run.sh"
echo ""
echo "  Then open http://localhost:8000"
echo ""
