#!/usr/bin/env bash
# Start egregore dev stack: API + workers + UI (no Langfuse by default).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SECRETS_FILE="$ROOT/../../deploy/.secrets/egregore-local.env"
if [[ -f "$SECRETS_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$SECRETS_FILE"
  set +a
fi

MPDIR="${PROMETHEUS_MULTIPROC_DIR:-/tmp/egregore-prom-multiproc}"
mkdir -p "$MPDIR"
export PROMETHEUS_MULTIPROC_DIR="$MPDIR"

wait_for_redis() {
  local host="${REDIS_HOST:-localhost}"
  local port="${REDIS_PORT:-6379}"
  local password="${REDIS_PASSWORD:-password}"
  local attempts=30
  echo "[dev] waiting for Redis at ${host}:${port}..."
  for _ in $(seq 1 "$attempts"); do
    if command -v redis-cli >/dev/null 2>&1; then
      if REDISCLI_AUTH="$password" redis-cli -h "$host" -p "$port" ping 2>/dev/null | grep -q PONG; then
        echo "[dev] redis ok"
        return 0
      fi
    elif docker ps --format '{{.Names}}' 2>/dev/null | grep -qx 'egregore-redis-1'; then
      if docker exec egregore-redis-1 redis-cli -a "$password" ping 2>/dev/null | grep -q PONG; then
        echo "[dev] redis ok (via docker)"
        return 0
      fi
    elif python3 -c "import socket; s=socket.create_connection(('$host', $port), 1); s.close()" 2>/dev/null; then
      echo "[dev] redis port open (skipping AUTH check)"
      return 0
    fi
    sleep 1
  done
  echo "[dev] WARN: Redis not reachable after ${attempts}s — workers may use in-memory queue fallback" >&2
  return 1
}

wait_for_redis || echo "[dev] WARN: starting API without confirmed Redis" >&2

REPLICAS="${WORKER_REPLICAS:-2}"
IDLE="${WORKER_IDLE_TIMEOUT:-0}"
PIDS=()

cleanup() {
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

echo "[dev] starting API on :8080"
(cd backend/api && PROMETHEUS_MULTIPROC_DIR="$MPDIR" uv run egregore serve --port 8080) &
PIDS+=($!)

if wait_for_redis; then
  for i in $(seq 1 "$REPLICAS"); do
    echo "[dev] starting worker $i/$REPLICAS"
    (cd backend/worker && PROMETHEUS_MULTIPROC_DIR="$MPDIR" uv run egregore worker --daemon --idle-timeout "$IDLE") &
    PIDS+=($!)
  done
else
  echo "[dev] ERROR: Redis unavailable — workers not started (queue would use memory fallback)" >&2
fi

echo "[dev] starting UI on :3000"
(cd web_ui && EGREGORE_API_UPSTREAM=http://127.0.0.1:8080 NEXT_PUBLIC_EGRESS_SSE=1 bun run dev) &
PIDS+=($!)

if command -v go >/dev/null && [[ -f tui/cmd/egregore-tui/main.go ]]; then
  echo "[dev] starting TUI (run in this terminal — attach manually if needed)"
  echo "[dev]   cd tui && make run"
fi

echo "[dev] API http://localhost:8080  UI http://localhost:3000  (Ctrl+C to stop)"
wait
