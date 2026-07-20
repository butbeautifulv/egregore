#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export USE_MEMORY_FALLBACK=true
export STAGE=test

echo "=== Domain (gated 100%) ==="
uv run pytest tests/domain/ -q --cov=cys_core/domain --cov-report=term-missing --cov-fail-under=100

echo "=== Application + infrastructure + delivery (batched, report only) ==="
rm -f .coverage
for batch in tests/application tests/contracts tests/integration tests/infrastructure \
  tests/ingress tests/workers tests/control tests/tool_gateway tests/bootstrap; do
  [[ -d "$batch" ]] || continue
  echo "--- $batch ---"
  uv run pytest "$batch" -q \
    --cov=cys_core/application \
    --cov=cys_core/infrastructure \
    --cov=interfaces \
    --cov-append || true
done
uv run coverage report --skip-covered || true
