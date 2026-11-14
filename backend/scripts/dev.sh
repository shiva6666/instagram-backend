#!/usr/bin/env bash
set -Eeuo pipefail

BACKEND_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd -- "$BACKEND_DIR/.." && pwd)"
RUN_DIR="$REPO_ROOT/.run"
BACKEND_PID_FILE="$RUN_DIR/backend.pid"
FRONTEND_PID_FILE="$RUN_DIR/frontend.pid"
cd "$BACKEND_DIR"

for command in docker uv npm node ps; do
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

mkdir -p "$RUN_DIR"

is_running_dev_process() {
  local pid_file="$1"
  local expected="$2"
  [[ -f "$pid_file" ]] || return 1
  local pid
  pid="$(cat "$pid_file")"
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  ps -p "$pid" -o args= 2>/dev/null | grep -Fq -- "$expected"
}

if is_running_dev_process "$BACKEND_PID_FILE" "uvicorn app.main:app" ||
   is_running_dev_process "$FRONTEND_PID_FILE" "vite --host 127.0.0.1"; then
  echo "A development server is already running. Run 'make stop' before starting it again." >&2
  exit 1
fi

rm -f "$BACKEND_PID_FILE" "$FRONTEND_PID_FILE"

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

cleanup() {
  echo
  echo "==> Stopping development servers..."
  bash "$BACKEND_DIR/scripts/stop.sh" --processes-only
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

echo "==> Starting FastAPI at http://127.0.0.1:8000 ..."
"$BACKEND_DIR/.venv/bin/uvicorn" app.main:app --reload --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!
printf '%s\n' "$BACKEND_PID" > "$BACKEND_PID_FILE"

echo "==> Starting Vite at http://127.0.0.1:5173 ..."
(
  cd "$REPO_ROOT/frontend"
  exec ./node_modules/.bin/vite --host 127.0.0.1
) &
FRONTEND_PID=$!
printf '%s\n' "$FRONTEND_PID" > "$FRONTEND_PID_FILE"

echo
echo "Both applications are running. Press Ctrl+C here or run 'make stop' in another terminal."
wait -n "$BACKEND_PID" "$FRONTEND_PID"
