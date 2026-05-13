#!/usr/bin/env bash
# GIAE one-command dev startup.
#
# Usage:  ./scripts/dev.sh
#
# What it does:
#   1. Kills any running GIAE uvicorn / celery / next dev processes
#   2. Loads .env so JWT_SECRET, DATABASE_URL, etc. are set
#   3. Marks stuck (>10 min PENDING/RUNNING) jobs as CANCELLED
#   4. Starts Redis (if not running)
#   5. Starts API (uvicorn) → port 8000
#   6. Starts Celery worker
#   7. Starts Next.js frontend → port 3000
#
# Ctrl-C kills everything cleanly.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "▶ GIAE dev startup"
echo "  repo: $ROOT"
echo

# ── 1. Kill leftovers ────────────────────────────────────────────────────────
echo "▶ Stopping any running GIAE processes…"
pkill -f "uvicorn giae_api"        2>/dev/null || true
pkill -f "celery -A giae_api"      2>/dev/null || true
pkill -f "celery.*giae_api.worker" 2>/dev/null || true
pkill -f "next dev"                2>/dev/null || true
pkill -f "node_modules/.bin/next"  2>/dev/null || true
sleep 2

# Make sure ports are free
if lsof -ti:8000 >/dev/null 2>&1; then
    echo "  port 8000 still busy — killing…"
    lsof -ti:8000 | xargs kill -9 2>/dev/null || true
fi
if lsof -ti:3000 >/dev/null 2>&1; then
    echo "  port 3000 still busy — killing…"
    lsof -ti:3000 | xargs kill -9 2>/dev/null || true
fi

# ── 2. Load env ──────────────────────────────────────────────────────────────
if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
    echo "▶ Loaded .env"
else
    echo "✗ No .env file found at $ROOT/.env"
    echo "  Create one with at least JWT_SECRET set."
    exit 1
fi

# Force sqlite for dev unless DATABASE_URL points at postgres
if [[ "${DATABASE_URL:-}" == *postgres* ]]; then
    echo "▶ Using Postgres: $DATABASE_URL"
else
    export DATABASE_URL="sqlite:///$ROOT/giae_api.db"
    echo "▶ Using SQLite: $DATABASE_URL"
fi

# ── 3. Clean stuck jobs ──────────────────────────────────────────────────────
echo "▶ Cleaning stale jobs…"
.venv/bin/python scripts/clean_stale_jobs.py

# ── 4. Redis ─────────────────────────────────────────────────────────────────
if ! pgrep -x redis-server >/dev/null; then
    echo "▶ Starting Redis…"
    redis-server --daemonize yes
    sleep 1
else
    echo "▶ Redis already running"
fi

# ── 5–7. Start API, worker, frontend ─────────────────────────────────────────
echo "▶ Starting API, worker, frontend (Ctrl-C to stop all)…"
echo

trap 'echo; echo "▶ Shutting down…"; kill 0 2>/dev/null; exit 0' INT TERM

PYTHONPATH=src .venv/bin/uvicorn giae_api.main:app --host 0.0.0.0 --port 8000 --reload &
PYTHONPATH=src .venv/bin/celery -A giae_api.worker.celery_app worker --loglevel=warning --pool=threads --concurrency=4 &
(cd frontend && /Users/atunraseayomide/Documents/GitHub/GIAE/frontend/node_modules/.bin/next dev --port 3000) &

wait
