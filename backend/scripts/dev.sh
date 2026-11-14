#!/usr/bin/env bash
set -Eeuo pipefail

BACKEND_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd -- "$BACKEND_DIR/.." && pwd)"
cd "$BACKEND_DIR"

for command in docker uv npm; do
  if ! command -v "$command" >/dev/null 2>&1; then
    echo "Error: '$command' is required to run the local development stack." >&2
    exit 1
  fi
done

if [[ ! -f "$REPO_ROOT/.env" ]]; then
  echo "Error: .env is missing. Run 'cp .env.example .env' and set AUTH_JWT_SECRET." >&2
  exit 1
fi

if grep -Eq '^AUTH_JWT_SECRET=(replace-with-a-random-secret-at-least-32-bytes)?$' "$REPO_ROOT/.env"; then
  echo "Error: set AUTH_JWT_SECRET in .env (at least 32 random bytes)." >&2
  echo "Generate one with: openssl rand -hex 32" >&2
  exit 1
fi

echo "==> Starting PostgreSQL and Redis..."
docker compose -f "$REPO_ROOT/docker-compose.yml" --env-file "$REPO_ROOT/.env" up --detach --wait postgres redis

echo "==> Syncing Python dependencies..."
uv sync --extra dev

echo "==> Applying database migrations..."
uv run alembic upgrade head

if [[ ! -d "$REPO_ROOT/frontend/node_modules" ]]; then
  echo "==> Installing frontend dependencies..."
  npm ci --prefix "$REPO_ROOT/frontend"
fi

echo "==> Starting FastAPI at http://127.0.0.1:8000 ..."
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

echo "==> Starting Vite at http://127.0.0.1:5173 ..."
(
  cd "$REPO_ROOT/frontend"
  npm run dev -- --host 127.0.0.1
) &
FRONTEND_PID=$!

cleanup() {
  echo
  echo "==> Stopping development servers..."
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
  wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

wait -n "$BACKEND_PID" "$FRONTEND_PID"
