#!/usr/bin/env bash
# Configure Langfuse LLM connection (vLLM / OpenAI-compatible) and LLM-as-a-Judge evaluators for egregore.
# Requires: Langfuse running (make dev-langfuse), projects/egregore/.env with LANGFUSE_* and LLM_*.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LF_DIR="$ROOT/deploy/langfuse"
EGREGORE_ENV="$ROOT/.env"

LF_USER_EMAIL="${LANGFUSE_INIT_USER_EMAIL:-dev@egregore.local}"
LF_USER_PASSWORD="${LANGFUSE_INIT_USER_PASSWORD:-egregore-dev}"
LF_PROJECT_ID="${LANGFUSE_INIT_PROJECT_ID:-egregore-dev}"

die() { echo "ERROR: $*" >&2; exit 1; }

[[ -f "$EGREGORE_ENV" ]] || die "Missing $EGREGORE_ENV — run make langfuse-dev-setup first"

# Read only needed keys — never `source` the full .env (REDIS_HOST=localhost breaks Langfuse containers).
read_env() {
  local key="$1"
  grep -E "^${key}=" "$EGREGORE_ENV" 2>/dev/null | head -1 | cut -d= -f2- || true
}

LANGFUSE_PUBLIC_KEY="$(read_env LANGFUSE_PUBLIC_KEY)"
LANGFUSE_SECRET_KEY="$(read_env LANGFUSE_SECRET_KEY)"
LANGFUSE_HOST="$(read_env LANGFUSE_HOST)"; LANGFUSE_HOST="${LANGFUSE_HOST:-http://localhost:3001}"
LLM_BASE_URL="$(read_env LLM_BASE_URL)"
LLM_MODEL="$(read_env LLM_MODEL)"
LF_PROVIDER="$(read_env LANGFUSE_LLM_PROVIDER)"; LF_PROVIDER="${LF_PROVIDER:-egregore-vllm}"
LF_SECRET_KEY="$(read_env LANGFUSE_LLM_SECRET_KEY)"; LF_SECRET_KEY="${LF_SECRET_KEY:-not-needed}"
JUDGE_SAMPLING="$(read_env LANGFUSE_JUDGE_SAMPLING)"; JUDGE_SAMPLING="${JUDGE_SAMPLING:-0.25}"

: "${LANGFUSE_PUBLIC_KEY:?LANGFUSE_PUBLIC_KEY required in .env}"
: "${LANGFUSE_SECRET_KEY:?LANGFUSE_SECRET_KEY required in .env}"
: "${LLM_BASE_URL:?LLM_BASE_URL required — set your vLLM / OpenAI-compatible endpoint}"
: "${LLM_MODEL:?LLM_MODEL required}"

LF_AUTH=(-u "${LANGFUSE_PUBLIC_KEY}:${LANGFUSE_SECRET_KEY}")
LF_API="${LANGFUSE_HOST}/api/public"

# Langfuse talks to vLLM directly (OpenAI schema) — strip LiteLLM provider prefix if present.
JUDGE_MODEL="${LLM_MODEL#*/}"
if MODELS_JSON="$(curl -fsS --max-time 10 "${LLM_BASE_URL%/}/models" 2>/dev/null)"; then
  DETECTED="$(python3 - <<'PY' "$MODELS_JSON" "$JUDGE_MODEL"
import json, sys
data = json.loads(sys.argv[1]).get("data", [])
want = sys.argv[2]
ids = [m.get("id", "") for m in data]
if want in ids:
    print(want)
elif ids:
    print(ids[0])
PY
)"
  [[ -n "$DETECTED" ]] && JUDGE_MODEL="$DETECTED"
fi

echo "==> Langfuse LLM-as-a-Judge setup (egregore)"
echo "    Langfuse: ${LANGFUSE_HOST}"
echo "    Judge:    ${JUDGE_MODEL} @ ${LLM_BASE_URL}"
echo "    Runtime:  ${LLM_MODEL} (egregore LiteLLM — unchanged)"

# --- 1. Whitelist vLLM host for self-hosted SSRF bypass ---
VLLM_HOST="$(python3 - <<'PY' "$LLM_BASE_URL"
import sys
from urllib.parse import urlparse
print(urlparse(sys.argv[1]).hostname or "")
PY
)"
[[ -n "$VLLM_HOST" ]] || die "Could not parse host from LLM_BASE_URL=$LLM_BASE_URL"

touch "$LF_DIR/.env"
set_lf_kv() {
  local key="$1" val="$2"
  if grep -q "^${key}=" "$LF_DIR/.env"; then
    sed -i "s|^${key}=.*|${key}=${val}|" "$LF_DIR/.env"
  else
    echo "${key}=${val}" >> "$LF_DIR/.env"
  fi
}

OLD_WHITELIST="$(grep '^LANGFUSE_LLM_CONNECTION_WHITELISTED_IPS=' "$LF_DIR/.env" 2>/dev/null | cut -d= -f2- || true)"
set_lf_kv LANGFUSE_LLM_CONNECTION_WHITELISTED_IPS "$VLLM_HOST"
if [[ "$VLLM_HOST" != "localhost" && "$VLLM_HOST" != "127.0.0.1" ]]; then
  set_lf_kv LANGFUSE_LLM_CONNECTION_WHITELISTED_HOST "localhost,127.0.0.1"
fi

if [[ "$OLD_WHITELIST" != "$VLLM_HOST" ]]; then
  echo "==> Whitelist updated ($VLLM_HOST) — recreating Langfuse web/worker..."
  (cd "$LF_DIR" && docker compose up -d --force-recreate langfuse-web langfuse-worker)
  for _ in $(seq 1 30); do
    if curl -fsS --max-time 3 "${LANGFUSE_HOST}/api/public/health" >/dev/null 2>&1; then
      break
    fi
    sleep 2
  done
fi

curl -fsS --max-time 10 "${LF_API}/health" >/dev/null || die "Langfuse not reachable at ${LANGFUSE_HOST}"

# --- 2. Upsert LLM connection ---
echo "==> Creating LLM connection provider=${LF_PROVIDER}..."
CONN_PAYLOAD="$(LF_PROVIDER="$LF_PROVIDER" LF_SECRET_KEY="$LF_SECRET_KEY" LLM_BASE_URL="$LLM_BASE_URL" JUDGE_MODEL="$JUDGE_MODEL" python3 - <<'PY'
import json, os
print(json.dumps({
    "provider": os.environ["LF_PROVIDER"],
    "adapter": "openai",
    "secretKey": os.environ["LF_SECRET_KEY"],
    "baseURL": os.environ["LLM_BASE_URL"],
    "withDefaultModels": False,
    "customModels": [os.environ["JUDGE_MODEL"]],
}))
PY
)"
CONN_RESP="$(curl -fsS --max-time 30 "${LF_AUTH[@]}" -X PUT "${LF_API}/llm-connections" \
  -H "Content-Type: application/json" -d "$CONN_PAYLOAD")"
CONN_ID="$(echo "$CONN_RESP" | python3 -c "import json,sys; print(json.load(sys.stdin).get('id',''))")"
echo "    LLM connection OK (id=${CONN_ID})"

# --- 3. Default evaluation model ---
echo "==> Setting default evaluation model..."
lf_login() {
  local csrf
  csrf="$(curl -fsS -c /tmp/lf_judge_cookies.txt "${LANGFUSE_HOST}/api/auth/csrf" | python3 -c "import json,sys; print(json.load(sys.stdin)['csrfToken'])")"
  curl -fsS -c /tmp/lf_judge_cookies.txt -b /tmp/lf_judge_cookies.txt -X POST "${LANGFUSE_HOST}/api/auth/callback/credentials" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    --data-urlencode "csrfToken=${csrf}" \
    --data-urlencode "email=${LF_USER_EMAIL}" \
    --data-urlencode "password=${LF_USER_PASSWORD}" \
    --data-urlencode "callbackUrl=${LANGFUSE_HOST}" \
    --data-urlencode "json=true" >/dev/null
}

set_default_model_db() {
  docker exec langfuse-postgres-1 psql -U postgres -d postgres -v ON_ERROR_STOP=1 -c "
    INSERT INTO default_llm_models (id, project_id, llm_api_key_id, provider, adapter, model, model_params)
    VALUES (
      'cmr1pjd00001qp076default1',
      '${LF_PROJECT_ID}',
      '${CONN_ID}',
      '${LF_PROVIDER}',
      'openai',
      '${JUDGE_MODEL}',
      '{\"temperature\": 0, \"max_tokens\": 4096}'::jsonb
    )
    ON CONFLICT (project_id) DO UPDATE SET
      llm_api_key_id = EXCLUDED.llm_api_key_id,
      provider = EXCLUDED.provider,
      adapter = EXCLUDED.adapter,
      model = EXCLUDED.model,
      model_params = EXCLUDED.model_params,
      updated_at = NOW();
  " >/dev/null
}

DEFAULT_OK=0
if lf_login 2>/dev/null; then
  TRPC_BODY="$(python3 - <<PY
import json
print(json.dumps({
    "json": {
        "projectId": "${LF_PROJECT_ID}",
        "provider": "${LF_PROVIDER}",
        "adapter": "openai",
        "model": "${JUDGE_MODEL}",
        "modelParams": {"temperature": 0, "max_tokens": 4096},
    }
}))
PY
)"
  TRPC_RESP="$(curl -m 90 -s -b /tmp/lf_judge_cookies.txt -X POST \
    "${LANGFUSE_HOST}/api/trpc/defaultLlmModel.upsertDefaultModel" \
    -H "Content-Type: application/json" \
    -d "$TRPC_BODY" || true)"
  if echo "$TRPC_RESP" | python3 -c "import json,sys; d=json.load(sys.stdin); sys.exit(0 if d.get('result') else 1)" 2>/dev/null; then
    echo "    Default evaluation model set via UI API (preflight OK)"
    DEFAULT_OK=1
  fi
fi

if [[ "$DEFAULT_OK" -eq 0 ]]; then
  echo "    UI preflight skipped or failed — writing default model directly (dev fallback)"
  set_default_model_db
  echo "    Default evaluation model: ${LF_PROVIDER} / ${JUDGE_MODEL}"
fi

# --- 4. LLM-as-a-Judge evaluation rules ---
create_rule() {
  local name="$1" evaluator="$2"
  local existing
  existing="$(curl -fsS --max-time 15 "${LF_AUTH[@]}" "${LF_API}/unstable/evaluation-rules?limit=100" | \
    python3 -c "import json,sys; rules=json.load(sys.stdin).get('data',[]); print(next((r['id'] for r in rules if r.get('name')=='${name}'), ''))" 2>/dev/null || true)"
  if [[ -n "$existing" ]]; then
    echo "    Rule '${name}' already exists (id=${existing}) — skip"
    return 0
  fi

  local payload
  payload="$(python3 - <<PY
import json
print(json.dumps({
    "name": "${name}",
    "evaluator": {"name": "${evaluator}", "scope": "managed"},
    "target": "observation",
    "enabled": True,
    "sampling": float("${JUDGE_SAMPLING}"),
    "filter": [
        {"type": "stringOptions", "column": "type", "operator": "any of", "value": ["GENERATION"]},
    ],
    "mapping": [
        {"variable": "query", "source": "input"},
        {"variable": "generation", "source": "output"},
    ],
}))
PY
)"
  if RESP="$(curl -fsS --max-time 60 "${LF_AUTH[@]}" -X POST "${LF_API}/unstable/evaluation-rules" \
      -H "Content-Type: application/json" -d "$payload" 2>&1)"; then
    echo "    Rule '${name}' → $(echo "$RESP" | python3 -c "import json,sys; print(json.load(sys.stdin).get('status','?'))")"
  else
    echo "    ERROR creating '${name}': ${RESP}"
    return 1
  fi
}

echo "==> Creating LLM-as-a-Judge evaluation rules (sampling=${JUDGE_SAMPLING})..."
create_rule "egregore-helpfulness" "Helpfulness"
create_rule "egregore-hallucination" "Hallucination"

echo ""
echo "Done. Open ${LANGFUSE_HOST} → Project Settings → LLM Connections / Evaluators."
echo "  Connection: ${LF_PROVIDER} → ${JUDGE_MODEL}"
echo "  Rules: egregore-helpfulness, egregore-hallucination on GENERATION observations"
echo "Re-run anytime: make langfuse-setup-judge"
