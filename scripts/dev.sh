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
docker compose up -d

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
