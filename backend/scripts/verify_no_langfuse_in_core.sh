#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if rg -n 'from langfuse|import langfuse' "$ROOT/src/cys_core" >/dev/null 2>&1; then
  echo "langfuse SDK imports found in cys_core:" >&2
  rg -n 'from langfuse|import langfuse' "$ROOT/src/cys_core" >&2 || true
  exit 1
fi
echo "OK: no langfuse imports in cys_core"
