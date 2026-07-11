#!/usr/bin/env bash
# Refresh shadcn/create preview reference for preset b3Rq8QejA (Lyra + neutral + lime).
#
# Usage:
#   ./scripts/sync-shadcn-create-ref.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${ROOT}/.external/shadcn-create-preset-b3Rq8QejA"
TMP="$(mktemp -d)"
PRESET="b3Rq8QejA"
REGISTRY_STYLE="base-lyra"

log() { printf '[sync-shadcn-create-ref] %s\n' "$*"; }

cleanup() { rm -rf "${TMP}"; }
trap cleanup EXIT

log "clone shadcn-ui (sparse) -> ${DEST}"
git clone --depth 1 --filter=blob:none --sparse https://github.com/shadcn-ui/ui.git "${TMP}/ui"
(
  cd "${TMP}/ui"
  git sparse-checkout set \
    "apps/v4/registry/bases/radix/blocks/preview" \
    "apps/v4/registry/bases/radix/blocks/preview-02" \
    "apps/v4/registry/bases/radix/blocks/preview-03" \
    "apps/v4/app/(app)/(create)"
)

mkdir -p "${DEST}"/{registry-json,blocks,create-ui,meta}

for block in preview preview-02 preview-03; do
  log "fetch registry ${REGISTRY_STYLE}/${block}.json"
  curl -fsSL --max-time 120 \
    "https://ui.shadcn.com/r/styles/${REGISTRY_STYLE}/${block}.json" \
    -o "${DEST}/registry-json/${block}.json"
done

rm -rf "${DEST}/blocks/preview" "${DEST}/blocks/preview-02" "${DEST}/blocks/preview-03"
cp -a "${TMP}/ui/apps/v4/registry/bases/radix/blocks/preview" "${DEST}/blocks/"
cp -a "${TMP}/ui/apps/v4/registry/bases/radix/blocks/preview-02" "${DEST}/blocks/"
cp -a "${TMP}/ui/apps/v4/registry/bases/radix/blocks/preview-03" "${DEST}/blocks/"

rm -rf "${DEST}/create-ui"
cp -a "${TMP}/ui/apps/v4/app/(app)/(create)" "${DEST}/create-ui/"

(
  cd "${ROOT}"
  npx --yes shadcn@latest preset decode "${PRESET}" > "${DEST}/meta/preset-decode.txt" 2>&1
)
cat > "${DEST}/meta/urls.txt" <<EOF
https://ui.shadcn.com/create?preset=${PRESET}
https://ui.shadcn.com/create?preset=${PRESET}&item=preview
EOF

log "done — $(find "${DEST}" -type f | wc -l) files in ${DEST}"
