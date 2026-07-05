#!/usr/bin/env bash
# Bootstrap catalog via API seed (Stream C cat-03).
# Usage:
#   EGREGORE_API_URL=http://localhost:8000 ./scripts/catalog_seed_bootstrap.sh
#   EGREGORE_API_TOKEN=... ./scripts/catalog_seed_bootstrap.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API_URL="${EGREGORE_API_URL:-http://localhost:8000}"
TOKEN="${EGREGORE_API_TOKEN:-}"

headers=(-H "Content-Type: application/json")
if [[ -n "$TOKEN" ]]; then
  headers+=(-H "Authorization: Bearer ${TOKEN}")
fi

echo "Seeding catalog at ${API_URL}/catalog/seed ..."
response="$(curl -fsS -X POST "${headers[@]}" "${API_URL}/catalog/seed")"
echo "$response" | python3 -c "import json,sys; d=json.load(sys.stdin); print('profile:', d.get('profile',{}).get('id')); print('seeded:', d.get('seeded'))"

profile_id="$(echo "$response" | python3 -c "import json,sys; print(json.load(sys.stdin).get('profile',{}).get('id',''))")"
if [[ "$profile_id" != "cybersec-soc" ]]; then
  echo "ERROR: expected profile cybersec-soc, got ${profile_id}" >&2
  exit 1
fi

echo "OK: catalog seeded (cybersec-soc)"
