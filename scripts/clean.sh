#!/usr/bin/env bash
# Remove regenerable cache artifacts from projects/egregore (contracts/worker/api split).
#
# Usage:
#   ./scripts/clean.sh           # cache only (default)
#   ./scripts/clean.sh cache
#   ./scripts/clean.sh venv-root
#   ./scripts/clean.sh all       # cache + root .venv (keeps each package's own .venv)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

MODE="${1:-cache}"

rm_path() {
  local path="$1"
  if [[ -e "$path" ]]; then
    echo "remove: $path"
    rm -rf "$path"
  else
    echo "skip: $path (missing)"
  fi
}

clean_legacy() {
  rm_path cys_core
  rm_path bootstrap
}

clean_tool_caches() {
  rm_path .pytest_cache
  rm_path .ruff_cache
  rm_path .import_linter_cache
  rm_path .coverage
  rm_path htmlcov
  rm -f .coverage.* 2>/dev/null || true

  for pkg in contracts worker api; do
    rm_path "backend/$pkg/.pytest_cache"
    rm_path "backend/$pkg/.ruff_cache"
    rm_path "backend/$pkg/.import_linter_cache"
    rm_path "backend/$pkg/.coverage"
    rm_path "backend/$pkg/htmlcov"
    rm -f "backend/$pkg/.coverage."* 2>/dev/null || true
  done
}

clean_build_artifacts() {
  rm_path build
  rm_path dist
  rm_path wheels
  for pkg in contracts worker api; do
    rm_path "backend/$pkg/build"
    rm_path "backend/$pkg/dist"
  done
  while IFS= read -r -d '' egg; do
    rm_path "$egg"
  done < <(find . -maxdepth 4 -type d -name '*.egg-info' -print0 2>/dev/null || true)
}

clean_pycache() {
  find . \
    \( -path './.venv' -o -path './backend/contracts/.venv' -o -path './backend/worker/.venv' \
       -o -path './backend/api/.venv' -o -path './web_ui' -o -path './.claude' \) -prune -o \
    -depth -type d -name '__pycache__' -print -exec rm -rf {} + 2>/dev/null || true

  find . \
    \( -path './.venv' -o -path './backend/contracts/.venv' -o -path './backend/worker/.venv' \
       -o -path './backend/api/.venv' -o -path './web_ui' -o -path './.claude' \) -prune -o \
    -type f \( -name '*.pyc' -o -name '*.pyo' \) -print -delete 2>/dev/null || true
}

clean_root_venv() {
  rm_path .venv
}

case "$MODE" in
  cache)
    clean_legacy
    clean_tool_caches
    clean_build_artifacts
    clean_pycache
    ;;
  venv-root)
    clean_root_venv
    ;;
  all)
    clean_legacy
    clean_tool_caches
    clean_build_artifacts
    clean_pycache
    clean_root_venv
    ;;
  -h|--help)
    sed -n '3,8p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
    ;;
  *)
    echo "unknown mode: $MODE (use cache|venv-root|all)" >&2
    exit 1
    ;;
esac

echo "clean.sh: done ($MODE)"
