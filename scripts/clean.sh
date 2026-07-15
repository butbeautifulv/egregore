#!/usr/bin/env bash
# Remove regenerable cache artifacts from projects/egregore (post api/ split).
#
# Usage:
#   ./scripts/clean.sh           # cache only (default)
#   ./scripts/clean.sh cache
#   ./scripts/clean.sh venv-root
#   ./scripts/clean.sh all       # cache + root .venv (keeps api/.venv)
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

  rm_path api/.pytest_cache
  rm_path api/.ruff_cache
  rm_path api/.import_linter_cache
  rm_path api/.coverage
  rm_path api/htmlcov
  rm -f api/.coverage.* 2>/dev/null || true
}

clean_build_artifacts() {
  rm_path build
  rm_path dist
  rm_path wheels
  rm_path api/build
  rm_path api/dist
  while IFS= read -r -d '' egg; do
    rm_path "$egg"
  done < <(find . -maxdepth 4 -type d -name '*.egg-info' -print0 2>/dev/null || true)
}

clean_pycache() {
  find . \
    \( -path './.venv' -o -path './api/.venv' -o -path './web_ui' -o -path './.claude' \) -prune -o \
    -depth -type d -name '__pycache__' -print -exec rm -rf {} + 2>/dev/null || true

  find . \
    \( -path './.venv' -o -path './api/.venv' -o -path './web_ui' -o -path './.claude' \) -prune -o \
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
