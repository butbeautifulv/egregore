#!/usr/bin/env bash
# Start egregore's dispatcher/agent-runtime split in "subprocess, same-host" mode
# (docs/MICROSERVICES_SPLIT_PLAN.md §1 item 1/2) — an alternative to scripts/dev.sh's
# `worker --daemon`, not a replacement: worker stays the deployed path until this is
# proven out end-to-end and a deliberate cutover retires it.
#
# EXECUTION_BACKEND=subprocess only works when dispatcher and agent-runtime share a
# filesystem (SubprocessExecutionBackend spawns `<AGENT_RUNTIME_PYTHON_EXECUTABLE> -m
# interfaces.cli.main run-sandboxed-job` as a child process, not a network call) — that
# rules out separate Docker containers without a shared volume trick, so this script
# runs both as plain host processes, same pattern scripts/dev.sh already uses for `api`/
# `worker`. Needs Postgres+Redis reachable (e.g. `docker compose -f deploy/docker-
# compose.yml up -d postgres redis`) and both packages' own `.venv` built (`uv sync` in
# each of backend/dispatcher and backend/agent-runtime).
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

AGENT_RUNTIME_VENV_PYTHON="$ROOT/backend/agent-runtime/.venv/bin/python"
if [[ ! -x "$AGENT_RUNTIME_VENV_PYTHON" ]]; then
  echo "[dev-split] backend/agent-runtime/.venv not found — run 'cd backend/agent-runtime && uv sync' first" >&2
  exit 1
fi

wait_for_redis() {
  local host="${REDIS_HOST:-localhost}"
  local port="${REDIS_PORT:-6379}"
  local password="${REDIS_PASSWORD:-password}"
  local attempts=30
  echo "[dev-split] waiting for Redis at ${host}:${port}..."
  for _ in $(seq 1 "$attempts"); do
    if command -v redis-cli >/dev/null 2>&1; then
      if REDISCLI_AUTH="$password" redis-cli -h "$host" -p "$port" ping 2>/dev/null | grep -q PONG; then
        echo "[dev-split] redis ok"
        return 0
      fi
    elif python3 -c "import socket; s=socket.create_connection(('$host', $port), 1); s.close()" 2>/dev/null; then
      echo "[dev-split] redis port open (skipping AUTH check)"
      return 0
    fi
    sleep 1
  done
  echo "[dev-split] ERROR: Redis not reachable after ${attempts}s" >&2
  return 1
}

wait_for_redis

PIDS=()
cleanup() {
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

echo "[dev-split] starting dispatcher (subprocess -> agent-runtime at $AGENT_RUNTIME_VENV_PYTHON)"
(
  cd backend/dispatcher
  EXECUTION_BACKEND=subprocess \
  AGENT_RUNTIME_PYTHON_EXECUTABLE="$AGENT_RUNTIME_VENV_PYTHON" \
  uv run egregore-dispatcher worker --daemon --idle-timeout "${DISPATCHER_IDLE_TIMEOUT:-0}"
) &
PIDS+=($!)

echo "[dev-split] dispatcher running, dispatching agent execution to agent-runtime per job (Ctrl+C to stop)"
wait
