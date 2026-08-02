#!/usr/bin/env bash
# Local/CI runner for the E2E suite: brings up backend infra (Postgres,
# Redis, Celery worker via docker compose), the FastAPI backend, and the
# Django frontend, waits for health, then leaves the stack running for
# `npx playwright test`. Call with `down` to tear everything back down.
#
# Assumes this script lives in ai-platform-frontend/scripts/ and that
# ai-platform-backend is checked out as a sibling directory (see
# CLAUDE.md workspace layout: ai-platform/{ai-platform-backend,ai-platform-frontend}).

set -euo pipefail

FRONTEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${E2E_BACKEND_DIR:-$FRONTEND_DIR/../ai-platform-backend}"
PID_DIR="$FRONTEND_DIR/.e2e-pids"
mkdir -p "$PID_DIR"

wait_for() {
  local url="$1" label="$2" attempts=30
  for _ in $(seq 1 "$attempts"); do
    if curl -fsS "$url" > /dev/null 2>&1; then
      echo "[test-e2e] $label is healthy"
      return 0
    fi
    sleep 2
  done
  echo "[test-e2e] $label did not become healthy in time" >&2
  return 1
}

up() {
  # Pre-create the uploads dir before the worker container's bind mount does.
  # The worker's Dockerfile has no USER directive, so it runs as root; if
  # `./uploads` doesn't exist yet when `docker compose up` starts it, Docker
  # auto-creates the bind-mount source on the host owned by root, and the
  # bare `uvicorn` process below (running as the current, non-root user)
  # then gets a silent PermissionError writing uploaded files -- surfacing
  # as an unhandled 500 on every document upload. Docker Desktop on macOS
  # doesn't hit this (its bind-mount layer maps to the host user), which is
  # why this only showed up in CI.
  mkdir -p "$BACKEND_DIR/uploads"

  echo "[test-e2e] Starting Postgres, Redis and Celery worker..."
  (cd "$BACKEND_DIR" && docker compose up -d postgres redis worker)

  # `docker compose up -d` returns once the container process launches, not
  # once Postgres has finished initializing and is accepting connections --
  # running alembic immediately after is a race that usually wins locally
  # (Postgres inits fast) but can lose on a colder CI runner, failing with
  # "the database system is starting up". Wait for real readiness instead.
  echo "[test-e2e] Waiting for Postgres to accept connections..."
  for _ in $(seq 1 30); do
    if (cd "$BACKEND_DIR" && docker compose exec -T postgres pg_isready -U "${POSTGRES_USER:-postgres}") > /dev/null 2>&1; then
      echo "[test-e2e] Postgres is ready"
      break
    fi
    sleep 1
  done

  echo "[test-e2e] Applying backend migrations..."
  (cd "$BACKEND_DIR" && alembic upgrade head)

  echo "[test-e2e] Starting FastAPI backend on :8000..."
  (cd "$BACKEND_DIR" && nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 \
    > "$PID_DIR/backend.log" 2>&1 & echo $! > "$PID_DIR/backend.pid")

  echo "[test-e2e] Starting Django frontend on :8001..."
  (cd "$FRONTEND_DIR" && python manage.py migrate --noinput)
  (cd "$FRONTEND_DIR" && nohup python manage.py runserver 0.0.0.0:8001 \
    > "$PID_DIR/frontend.log" 2>&1 & echo $! > "$PID_DIR/frontend.pid")

  wait_for "http://localhost:8000/health" "backend"
  wait_for "http://localhost:8001/health/" "frontend"

  echo "[test-e2e] Seeding deterministic E2E test users (idempotent)..."
  (cd "$BACKEND_DIR" && python - <<'PYEOF' || true
import os, sys
sys.path.insert(0, ".")
# Best-effort seed: relies on the backend's own register endpoint being
# idempotent-safe to call repeatedly (duplicate registration returns an
# error we ignore here). Replace with a dedicated seed script if the
# backend adds one.
import httpx
users = [
    (os.environ.get("E2E_USER_EMAIL"), os.environ.get("E2E_USER_PASSWORD")),
    (os.environ.get("E2E_SECONDARY_USER_EMAIL"), os.environ.get("E2E_SECONDARY_USER_PASSWORD")),
]
for email, password in users:
    if not email or not password:
        continue
    try:
        httpx.post("http://localhost:8000/auth/register", json={"email": email, "password": password}, timeout=10)
    except Exception as exc:
        print(f"seed warning for {email}: {exc}")
PYEOF
  )

  echo "[test-e2e] Stack is up. Run: npx playwright test"
}

down() {
  echo "[test-e2e] Stopping frontend/backend processes..."
  for pidfile in "$PID_DIR"/*.pid; do
    [ -f "$pidfile" ] || continue
    kill "$(cat "$pidfile")" 2>/dev/null || true
    rm -f "$pidfile"
  done

  echo "[test-e2e] Stopping docker compose services..."
  (cd "$BACKEND_DIR" && docker compose down)
}

case "${1:-}" in
  up) up ;;
  down) down ;;
  *)
    echo "Usage: $0 {up|down}" >&2
    exit 1
    ;;
esac
