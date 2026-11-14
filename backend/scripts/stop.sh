#!/usr/bin/env bash
set -Eeuo pipefail

BACKEND_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd -- "$BACKEND_DIR/.." && pwd)"
RUN_DIR="$REPO_ROOT/.run"

stop_process() {
  local label="$1"
  local pid_file="$2"
  local expected="$3"

  if [[ ! -f "$pid_file" ]]; then
    echo "==> $label: no PID file; already stopped."
    return
  fi

  local pid
  pid="$(cat "$pid_file")"
  if [[ ! "$pid" =~ ^[0-9]+$ ]] || ! kill -0 "$pid" 2>/dev/null; then
    echo "==> $label: process is not running."
    rm -f "$pid_file"
    return
  fi

  local command_line
  command_line="$(ps -p "$pid" -o args= 2>/dev/null || true)"
  if [[ "$command_line" != *"$expected"* ]]; then
    echo "==> $label: PID $pid no longer belongs to this dev server; leaving it untouched."
    rm -f "$pid_file"
    return
  fi

  echo "==> Stopping $label (PID $pid)..."
  kill -TERM "$pid"

  for _ in {1..25}; do
    kill -0 "$pid" 2>/dev/null || break
    command_line="$(ps -p "$pid" -o args= 2>/dev/null || true)"
    [[ "$command_line" == *"$expected"* ]] || break
    sleep 0.2
  done

  if kill -0 "$pid" 2>/dev/null; then
    command_line="$(ps -p "$pid" -o args= 2>/dev/null || true)"
    if [[ "$command_line" == *"$expected"* ]]; then
      echo "==> $label did not stop gracefully; sending SIGKILL."
      kill -KILL "$pid" 2>/dev/null || true
    fi
  fi

  rm -f "$pid_file"
}

stop_process "FastAPI" "$RUN_DIR/backend.pid" "uvicorn app.main:app"
stop_process "Vite" "$RUN_DIR/frontend.pid" "vite --host 127.0.0.1"
rmdir "$RUN_DIR" 2>/dev/null || true

if [[ "${1:-}" == "--processes-only" ]]; then
  exit 0
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Error: Docker is required to stop the Docker Compose services." >&2
  exit 1
fi

echo "==> Stopping all Docker Compose services (named volumes are preserved)..."
cd "$REPO_ROOT"
docker compose down --remove-orphans

echo "==> Development stack stopped."
