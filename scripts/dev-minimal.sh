#!/usr/bin/env bash
# API + worker with deploy secrets; ui-minimal on :5173 (no Next.js).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SECRETS_FILE="$ROOT/../../deploy/.secrets/egregore-local.env"
if [[ -f "$SECRETS_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$SECRETS_FILE"
  set +a
else
  echo "[dev-minimal] WARN: missing $SECRETS_FILE" >&2
fi

MPDIR="${PROMETHEUS_MULTIPROC_DIR:-/tmp/egregore-prom-multiproc}"
mkdir -p "$MPDIR"
export PROMETHEUS_MULTIPROC_DIR="$MPDIR"

PIDS=()
cleanup() {
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

echo "[dev-minimal] API http://localhost:8080"
PROMETHEUS_MULTIPROC_DIR="$MPDIR" uv run egregore serve --port 8080 &
PIDS+=($!)

echo "[dev-minimal] worker"
PROMETHEUS_MULTIPROC_DIR="$MPDIR" uv run egregore worker --daemon --idle-timeout 0 &
PIDS+=($!)

echo "[dev-minimal] ui-minimal http://localhost:5173"
if curl -sf http://localhost:5173/ >/dev/null 2>&1; then
  echo "[dev-minimal] ui-minimal already running on :5173"
else
  (cd ui-minimal && python3 -m http.server 5173) &
  PIDS+=($!)
fi

echo "[dev-minimal] ready (Ctrl+C to stop)"
wait
