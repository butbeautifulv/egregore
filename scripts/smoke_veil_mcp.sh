#!/usr/bin/env bash
# Smoke: veil-mcp health + MCP tools/list (requires stack on :8091).
set -euo pipefail

BASE="${VEIL_MCP_URL:-http://localhost:8091}"
HEALTH_URL="${BASE%/mcp}/health"
MCP_URL="${BASE%/}/mcp"

if ! curl -sf -m 5 "$HEALTH_URL" >/dev/null; then
  echo "FAIL: health check $HEALTH_URL" >&2
  exit 1
fi
echo "OK: $HEALTH_URL"

payload='{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
response="$(curl -sf -m 15 -X POST "$MCP_URL" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json' \
  -d "$payload")"

if echo "$response" | grep -q 'playbook_search'; then
  echo "OK: tools/list includes playbook_search"
else
  echo "FAIL: playbook_search not in tools/list" >&2
  echo "$response" | head -c 500 >&2
  exit 1
fi

health_payload='{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"ti_health","arguments":{}}}'
health_response="$(curl -sf -m 15 -X POST "$MCP_URL" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json' \
  -d "$health_payload")"
if echo "$health_response" | grep -q '"result"'; then
  echo "OK: ti_health tools/call"
else
  echo "WARN: ti_health call did not return result (Neo4j may be empty)" >&2
fi
