#!/usr/bin/env bash
# Refactor PR gate: lock, lint, import boundaries, core pytest batches.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export STAGE="${STAGE:-test}"
export USE_MEMORY_FALLBACK="${USE_MEMORY_FALLBACK:-true}"

echo "==> uv lock --check"
uv lock --check

echo "==> ruff check"
uv run ruff check .

echo "==> import boundaries"
uv run python scripts/verify_import_boundaries.py

echo "==> pytest batches (architecture, contracts, infrastructure, application, api, worker)"
./scripts/pytest_batches.sh tests/architecture tests/arch tests/contracts
./scripts/pytest_batches.sh tests/infrastructure tests/application tests/api tests/worker

echo "OK: refactor checks passed"
