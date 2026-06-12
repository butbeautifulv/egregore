#!/usr/bin/env bash
# Run pytest in separate processes per tests/<dir>/ so memory is freed between batches.
#
# Usage:
#   ./scripts/pytest_batches.sh                    # all batches, no coverage
#   ./scripts/pytest_batches.sh --cov              # append coverage, report at end
#   ./scripts/pytest_batches.sh --cov --domain-gate  # domain batch fails under 100%
#   ./scripts/pytest_batches.sh tests/domain tests/ingress
#   ./scripts/pytest_batches.sh -- -k test_api     # extra pytest args after --
#
# Env:
#   STAGE=test  USE_MEMORY_FALLBACK=true  (defaults set below)
#   PYTEST_BATCH_ORDER=domain,integration,...  (optional override)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export USE_MEMORY_FALLBACK="${USE_MEMORY_FALLBACK:-true}"
export STAGE="${STAGE:-test}"

WITH_COV=0
DOMAIN_GATE=0
EXTRA_PYTEST=()
USER_PATHS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --cov)
      WITH_COV=1
      shift
      ;;
    --domain-gate)
      DOMAIN_GATE=1
      WITH_COV=1
      shift
      ;;
    --)
      shift
      EXTRA_PYTEST=("$@")
      break
      ;;
    -h|--help)
      sed -n '3,12p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      USER_PATHS+=("$1")
      shift
      ;;
  esac
done

_discover_batches() {
  if [[ ${#USER_PATHS[@]} -gt 0 ]]; then
    printf '%s\n' "${USER_PATHS[@]}"
    return
  fi
  if [[ -n "${PYTEST_BATCH_ORDER:-}" ]]; then
    local name
    IFS=',' read -ra _order <<< "$PYTEST_BATCH_ORDER"
    for name in "${_order[@]}"; do
      echo "tests/${name}"
    done
    return
  fi
  local dir
  for dir in "$ROOT"/tests/*/; do
    local name
    name="$(basename "$dir")"
    [[ "$name" == "__pycache__" ]] && continue
    if find "$dir" -name 'test_*.py' -print -quit | grep -q .; then
      echo "tests/$name"
    fi
  done
}

mapfile -t BATCHES < <(_discover_batches)

if [[ ${#BATCHES[@]} -eq 0 ]]; then
  echo "pytest_batches: no test directories found" >&2
  exit 1
fi

if [[ "$WITH_COV" == 1 ]]; then
  rm -f .coverage
fi

FAILED=0
RAN=0

for batch in "${BATCHES[@]}"; do
  if [[ ! -d "$batch" ]]; then
    echo "=== skip (missing): $batch ==="
    continue
  fi

  COV_ARGS=()
  if [[ "$WITH_COV" == 1 ]]; then
    COV_ARGS=(
      --cov=cys_core/domain
      --cov=cys_core/application
      --cov=cys_core/infrastructure
      --cov-append
      --cov-fail-under=0
    )
  fi

  echo ""
  echo "=== pytest batch: $batch ==="
  RAN=$((RAN + 1))
  if uv run pytest "$batch" -q "${COV_ARGS[@]}" "${EXTRA_PYTEST[@]}"; then
    echo "=== OK: $batch ==="
  else
    echo "=== FAIL: $batch ===" >&2
    FAILED=$((FAILED + 1))
    if [[ "${FAIL_FAST:-}" == 1 ]]; then
      break
    fi
  fi
done

if [[ "$DOMAIN_GATE" == 1 ]]; then
  echo ""
  echo "=== domain coverage gate (100%) ==="
  if [[ ! -f .coverage ]]; then
    echo "pytest_batches: missing .coverage (run with --cov first)" >&2
    FAILED=$((FAILED + 1))
  elif ! uv run coverage report --include="cys_core/domain/*" --fail-under=100; then
    FAILED=$((FAILED + 1))
  fi
fi

if [[ "$WITH_COV" == 1 && -f .coverage ]]; then
  echo ""
  echo "=== combined coverage ==="
  uv run coverage report --skip-covered || true
fi

echo ""
echo "pytest_batches: $RAN batch(es), $FAILED failed"
[[ "$FAILED" -eq 0 ]]
