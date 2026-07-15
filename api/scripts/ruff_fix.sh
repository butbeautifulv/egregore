#!/usr/bin/env bash
# Auto-fix lint (imports, unused imports) and format. Run before commit.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== ruff check --select I --fix (organize imports) ==="
uv run ruff check --select I --fix .

echo "=== ruff check --fix (lint) ==="
uv run ruff check --fix .

echo "=== ruff format ==="
uv run ruff format .

echo "=== ruff check (verify) ==="
uv run ruff check .

echo "ruff: OK"
