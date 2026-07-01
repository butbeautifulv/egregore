#!/usr/bin/env bash
# Dev stack: infra + supervised API + scaled worker daemons + UI.
# Processes auto-restart on crash; workers run until stopped (WORKER_IDLE_TIMEOUT=0).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

WORKER_REPLICAS="${WORKER_REPLICAS:-2}"
WORKER_IDLE_TIMEOUT="${WORKER_IDLE_TIMEOUT:-0}"

export PROMETHEUS_MULTIPROC_DIR="${PROMETHEUS_MULTIPROC_DIR:-/tmp/egregore-prom-multiproc}"
rm -rf "$PROMETHEUS_MULTIPROC_DIR"
mkdir -p "$PROMETHEUS_MULTIPROC_DIR"

SUPERVISOR_PIDS=()

cleanup() {
  for pid in "${SUPERVISOR_PIDS[@]}"; do
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
}
trap cleanup EXIT INT TERM

start_supervised() {
  local name="$1"
  shift
  (
    while true; do
      echo "[dev] starting ${name}..."
      "$@" || echo "[dev] ${name} exited ($?), restarting in 2s"
      sleep 2
    done
  ) &
  SUPERVISOR_PIDS+=("$!")
}

echo "Starting infrastructure (docker compose)..."
docker compose up -d postgres redis qdrant

wait_for_postgres() {
  local host="${POSTGRES_HOST:-localhost}"
  local port="${POSTGRES_PORT:-5432}"
  local user="${POSTGRES_USER:-postgres}"
  local tries=0
  until docker compose exec -T postgres pg_isready -U "$user" -h localhost -p 5432 >/dev/null 2>&1; do
    tries=$((tries + 1))
    if [[ $tries -ge 30 ]]; then
      echo "[dev] WARN: postgres not healthy after 60s — API may fail until DB is up"
      return 1
    fi
    sleep 2
  done
  echo "[dev] postgres is ready (${host}:${port})"
}

wait_for_redis() {
  local password="${REDIS_PASSWORD:-password}"
  local tries=0
  until docker compose exec -T redis redis-cli -a "$password" ping 2>/dev/null | grep -q PONG; do
    tries=$((tries + 1))
    if [[ $tries -ge 30 ]]; then
      echo "[dev] WARN: redis not healthy after 60s — job queue may fail until Redis is up"
      return 1
    fi
    sleep 2
  done
  echo "[dev] redis is ready"
}

wait_for_postgres || true
wait_for_redis || true

if [[ -n "${LLM_BASE_URL:-}" ]]; then
  models_url="${LLM_BASE_URL%/}/models"
  if ! curl -sf -m 5 -H "Authorization: Bearer ${LLM_API_KEY:-EMPTY}" "$models_url" >/dev/null 2>&1; then
    echo "[dev] WARN: LLM endpoint unreachable at ${models_url} — planner will use fallback after timeout"
  else
    echo "[dev] LLM endpoint OK: ${models_url}"
  fi
fi

if [[ ! -d ui/node_modules ]]; then
  echo "Installing UI dependencies..."
  (cd ui && npm install)
fi

echo "Starting API on :8080 (supervised)..."
start_supervised api uv run egregore serve --port 8080

echo "Starting ${WORKER_REPLICAS} worker daemon(s) (idle-timeout=${WORKER_IDLE_TIMEOUT})..."
for i in $(seq 1 "$WORKER_REPLICAS"); do
  start_supervised "worker-${i}" uv run egregore worker --daemon --idle-timeout "$WORKER_IDLE_TIMEOUT"
done

echo ""
echo "Stack running:"
echo "  API:     http://localhost:8080"
echo "  UI:      http://localhost:3000"
echo "  Workers: ${WORKER_REPLICAS} replicas (supervised, auto-restart)"
echo "Press Ctrl+C to stop."
echo ""

echo "Starting UI on :3000..."
(cd ui && npm run dev)
