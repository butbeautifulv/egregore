#!/usr/bin/env bash
# Configure Langfuse LLM connection + default eval model + Helpfulness/Hallucination judges.
#
# Mirrors local dev setup described in docs/OBSERVABILITY.md.
#
# Usage (local):
#   LANGFUSE_HOST=http://localhost:3001 \
#   LANGFUSE_PUBLIC_KEY=pk-lf-... LANGFUSE_SECRET_KEY=sk-lf-... \
#   LANGFUSE_USER_EMAIL=dev@egregore.local LANGFUSE_USER_PASSWORD=egregore-dev \
#   LLM_BASE_URL=http://10.8.185.185:11611/v1 \
#   LLM_MODEL=openai/Kbenkhaled/Qwen3.5-27B-NVFP4 \
#   ./scripts/langfuse-setup-llm-judge.sh
#
# Env:
#   LANGFUSE_HOST              Langfuse base URL (no trailing slash)
#   LANGFUSE_PUBLIC_KEY        project public key (public API auth)
#   LANGFUSE_SECRET_KEY        project secret key (public API auth)
#   LANGFUSE_USER_EMAIL        UI user for tRPC session (default: dev@egregore.local)
#   LANGFUSE_USER_PASSWORD     UI password (default: egregore-dev)
#   LANGFUSE_PROJECT_ID        project id (default: egregore-dev)
#   LLM_BASE_URL               OpenAI-compatible vLLM base URL
#   LLM_MODEL                  egregore/litellm model id (openai/ prefix ok)
#   LANGFUSE_LLM_PROVIDER      connection name in Langfuse (default: egregore-vllm)
#   LANGFUSE_JUDGE_SAMPLING    live eval sampling 0..1 (default: 0.25)
#   LANGFUSE_INSECURE_TLS      set to 1 for self-signed TLS (k3s offline)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

HOST="${LANGFUSE_HOST:-http://localhost:3001}"
HOST="${HOST%/}"
PUB="${LANGFUSE_PUBLIC_KEY:-pk-lf-egregore-dev-local}"
SEC="${LANGFUSE_SECRET_KEY:-sk-lf-egregore-dev-local}"
USER_EMAIL="${LANGFUSE_USER_EMAIL:-dev@egregore.local}"
USER_PASSWORD="${LANGFUSE_USER_PASSWORD:-egregore-dev}"
PROJECT_ID="${LANGFUSE_PROJECT_ID:-egregore-dev}"
LLM_BASE_URL="${LLM_BASE_URL:-}"
LLM_MODEL="${LLM_MODEL:-}"
PROVIDER="${LANGFUSE_LLM_PROVIDER:-egregore-vllm}"
SAMPLING="${LANGFUSE_JUDGE_SAMPLING:-0.25}"
INSECURE="${LANGFUSE_INSECURE_TLS:-0}"

COOKIE_JAR="$(mktemp)"
trap 'rm -f "${COOKIE_JAR}"' EXIT

log() { printf '[langfuse-judge] %s\n' "$*"; }

curl_common() {
  local args=(-sS -b "${COOKIE_JAR}" -c "${COOKIE_JAR}")
  if [[ "${INSECURE}" == "1" ]]; then
    args+=(-k)
  fi
  curl "${args[@]}" "$@"
}

public_api() {
  local method="$1" path="$2" body="${3:-}"
  local args=(-sS -u "${PUB}:${SEC}")
  if [[ "${INSECURE}" == "1" ]]; then
    args+=(-k)
  fi
  if [[ -n "${body}" ]]; then
    curl "${args[@]}" -H "Content-Type: application/json" -X "${method}" "${HOST}${path}" -d "${body}"
  else
    curl "${args[@]}" -X "${method}" "${HOST}${path}"
  fi
}

trpc_post() {
  local proc="$1" body="$2" timeout="${3:-120}"
  curl_common --max-time "${timeout}" -H "Content-Type: application/json" \
    -X POST "${HOST}/api/trpc/${proc}" -d "${body}"
}

trpc_get() {
  local proc="$1" input="$2"
  local enc
  enc="$(python3 -c 'import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))' "${input}")"
  curl_common "${HOST}/api/trpc/${proc}?batch=1&input=${enc}"
}

login_session() {
  local csrf
  csrf="$(curl_common "${HOST}/api/auth/csrf" | python3 -c 'import json,sys; print(json.load(sys.stdin)["csrfToken"])')"
  curl_common -H "Content-Type: application/x-www-form-urlencoded" \
    -X POST "${HOST}/api/auth/callback/credentials" \
    --data-urlencode "csrfToken=${csrf}" \
    --data-urlencode "email=${USER_EMAIL}" \
    --data-urlencode "password=${USER_PASSWORD}" \
    --data-urlencode "callbackUrl=${HOST}" \
    --data-urlencode "json=true" >/dev/null
}

langfuse_model_id() {
  local model="$1"
  model="${model#openai/}"
  printf '%s' "${model}"
}

need_llm_env() {
  if [[ -z "${LLM_BASE_URL}" || -z "${LLM_MODEL}" ]]; then
    if [[ -f "${ROOT}/.env" ]]; then
      # shellcheck disable=SC1091
      set -a; source "${ROOT}/.env"; set +a
      LLM_BASE_URL="${LLM_BASE_URL:-}"
      LLM_MODEL="${LLM_MODEL:-}"
    fi
  fi
  if [[ -z "${LLM_BASE_URL}" || -z "${LLM_MODEL}" ]]; then
    echo "missing LLM_BASE_URL / LLM_MODEL" >&2
    exit 2
  fi
}

ensure_llm_connection() {
  local model_id="$1"
  local payload
  payload="$(python3 - <<PY
import json
print(json.dumps({
  "provider": "${PROVIDER}",
  "adapter": "openai",
  "secretKey": "dummy",
  "baseURL": "${LLM_BASE_URL}",
  "customModels": ["${model_id}"],
  "withDefaultModels": False,
}))
PY
)"
  public_api PUT /api/public/llm-connections "${payload}" >/dev/null
  log "LLM connection ${PROVIDER} -> ${LLM_BASE_URL} (${model_id})"
}

ensure_default_eval_model() {
  local model_id="$1"
  local body
  body="$(python3 - <<PY
import json
print(json.dumps({"json": {
  "projectId": "${PROJECT_ID}",
  "provider": "${PROVIDER}",
  "adapter": "openai",
  "model": "${model_id}",
  "modelParams": {"temperature": 0},
}}))
PY
)"
  local resp
  resp="$(trpc_post defaultLlmModel.upsertDefaultModel "${body}" 180)"
  if echo "${resp}" | grep -q '"error"'; then
    echo "${resp}" >&2
    exit 1
  fi
  log "default evaluation model: ${PROVIDER} / ${model_id}"
}

template_exists() {
  local name="$1"
  local input resp count
  input="$(python3 - <<PY
import json
print(json.dumps({"0":{"json":{"projectId":"${PROJECT_ID}","name":"${name}","isUserManaged":True}}}))
PY
)"
  resp="$(trpc_get evals.allTemplatesForName "${input}")"
  count="$(echo "${resp}" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(len(d[0]["result"]["data"]["json"]["templates"]))' 2>/dev/null || echo 0)"
  [[ "${count}" != "0" ]]
}

create_template() {
  local name="$1" prompt="$2" score_desc="$3"
  local body
  body="$(python3 - <<PY
import json
print(json.dumps({"json": {
  "projectId": "${PROJECT_ID}",
  "name": "${name}",
  "prompt": """${prompt}""",
  "vars": ["input", "output"],
  "outputDefinition": {
    "dataType": "NUMERIC",
    "score": "${score_desc}",
    "reasoning": "Explain why this score was assigned.",
  },
}}))
PY
)"
  trpc_post evals.createTemplate "${body}" 180 | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["result"]["data"]["json"]["id"])'
}

ensure_eval_job() {
  local template_id="$1" score_name="$2"
  local body
  body="$(python3 - <<PY
import json
print(json.dumps({"json": {
  "projectId": "${PROJECT_ID}",
  "evalTemplateId": "${template_id}",
  "scoreName": "${score_name}",
  "target": "event",
  "filter": [{
    "type": "stringOptions",
    "column": "type",
    "operator": "any of",
    "value": ["GENERATION"],
  }],
  "mapping": [
    {"variable": "input", "templateVariable": "input", "langfuseObject": "generation", "selectedColumnId": "input"},
    {"variable": "output", "templateVariable": "output", "langfuseObject": "generation", "selectedColumnId": "output"},
  ],
  "sampling": float("${SAMPLING}"),
  "delay": 0,
  "timeScope": ["NEW"],
  "status": "ACTIVE",
}}))
PY
)"
  trpc_post evals.createJob "${body}" 60 >/dev/null
  log "eval job active: ${score_name} (GENERATION, sampling=${SAMPLING})"
}

main() {
  need_llm_env
  local model_id
  model_id="$(langfuse_model_id "${LLM_MODEL}")"

  if ! public_api GET /api/public/health >/dev/null 2>&1; then
    echo "[langfuse-judge] Langfuse not reachable at ${HOST}" >&2
    exit 1
  fi

  ensure_llm_connection "${model_id}"
  login_session
  ensure_default_eval_model "${model_id}"

  local helpful_id halluc_id
  if template_exists Helpfulness; then
    helpful_id="$(trpc_get evals.allTemplatesForName "$(python3 -c 'import json; print(json.dumps({"0":{"json":{"projectId":"'${PROJECT_ID}'","name":"Helpfulness","isUserManaged":True}}}))')" \
      | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d[0]["result"]["data"]["json"]["templates"][0]["id"])')"
    log "template exists: Helpfulness"
  else
    helpful_id="$(create_template Helpfulness \
      "You are an expert evaluator. Score helpfulness from 0 to 1.\n\nInput:\n{{input}}\n\nOutput:\n{{output}}" \
      "Helpfulness score between 0 and 1.")"
    log "created template: Helpfulness"
  fi

  if template_exists Hallucination; then
    halluc_id="$(trpc_get evals.allTemplatesForName "$(python3 -c 'import json; print(json.dumps({"0":{"json":{"projectId":"'${PROJECT_ID}'","name":"Hallucination","isUserManaged":True}}}))')" \
      | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d[0]["result"]["data"]["json"]["templates"][0]["id"])')"
    log "template exists: Hallucination"
  else
    halluc_id="$(create_template Hallucination \
      "You are an expert evaluator. Score hallucination risk from 0 (grounded) to 1 (hallucinated).\n\nInput:\n{{input}}\n\nOutput:\n{{output}}" \
      "Hallucination score between 0 and 1.")"
    log "created template: Hallucination"
  fi

  # createJob is idempotent by unique score names per project in practice; ignore conflicts
  ensure_eval_job "${helpful_id}" helpfulness || true
  ensure_eval_job "${halluc_id}" hallucination || true

  log "done — Langfuse Playground + LLM-as-Judge wired to ${LLM_BASE_URL}"
}

main "$@"
