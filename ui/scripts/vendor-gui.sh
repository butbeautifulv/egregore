#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEFAULT_GUI_SRC="$ROOT/../../../shared/gui/src"
GUI_PKG_ROOT="$ROOT/../../../shared/gui"
GUI_SRC="${GUI_SRC:-$DEFAULT_GUI_SRC}"

if [[ ! -d "$GUI_SRC" ]]; then
  echo "GUI source not found: $GUI_SRC" >&2
  echo "Set GUI_SRC to shared/gui/src (meta-repo checkout) or use committed vendor/gui/." >&2
  exit 1
fi

VENDOR="$ROOT/vendor/gui"
DIRS=(shell theme motion hooks ui layout data-table lib/data-table lib/datetime)
FILES=(utils.ts)

mkdir -p "$VENDOR"
for dir in "${DIRS[@]}"; do
  mkdir -p "$VENDOR/$dir"
  rsync -a --delete "$GUI_SRC/$dir/" "$VENDOR/$dir/"
done
for file in "${FILES[@]}"; do
  cp "$GUI_SRC/$file" "$VENDOR/$file"
done

STYLE_PROFILES="${GUI_PKG_ROOT}/gui-style-profiles.css"
if [[ -f "$STYLE_PROFILES" ]]; then
  cp "$STYLE_PROFILES" "$ROOT/vendor/gui-style-profiles.css"
fi

echo "Vendored gui from $GUI_SRC -> $VENDOR"
echo "Rewriting imports..."
node "$ROOT/scripts/rewrite-vendor-imports.mjs"
