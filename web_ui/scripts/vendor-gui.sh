#!/usr/bin/env bash
set -euo pipefail

# vendor/gui is Egregore's own, hand-edited component library now (see
# docs/GUI_VENDOR.md) — this script is only for the rare, deliberate case of
# pulling one specific update in from shared/gui. It is NOT a routine step,
# and it rsyncs with --delete, which would silently wipe local edits under
# vendor/gui, so it refuses to run over an uncommitted tree.

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEFAULT_GUI_SRC="$ROOT/../../../shared/gui/src"
GUI_PKG_ROOT="$ROOT/../../../shared/gui"
GUI_SRC="${GUI_SRC:-$DEFAULT_GUI_SRC}"
VENDOR="$ROOT/vendor/gui"

if [[ ! -d "$GUI_SRC" ]]; then
  echo "GUI source not found: $GUI_SRC" >&2
  echo "Set GUI_SRC to shared/gui/src (meta-repo checkout), or skip this — vendor/gui is self-contained and doesn't need it." >&2
  exit 1
fi

if git -C "$ROOT" status --porcelain -- vendor/gui 2>/dev/null | grep -q .; then
  echo "vendor/gui has uncommitted changes — commit or stash them first." >&2
  echo "This script rsyncs with --delete and would silently overwrite local edits." >&2
  exit 1
fi

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

echo "Pulled an update from $GUI_SRC -> $VENDOR"
echo "Rewriting imports..."
node "$ROOT/scripts/rewrite-vendor-imports.mjs"
echo "Review the diff before committing — rsync --delete may have removed local-only files."
