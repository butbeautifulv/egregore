#!/usr/bin/env bash
# Smoke-test Veil MCP HTTP endpoint (local compose or k3s in-cluster).
#
# Usage:
#   make cxado-smoke-veil-mcp
#   make cxado-smoke-veil-mcp-k3s CXADO_OFFLINE_SSH_HOST=bbv-p30-wifi
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
# shellcheck source=scripts/k8s/cxado-offline-env.sh
source "${ROOT}/scripts/k8s/cxado-offline-env.sh" 2>/dev/null || true

VEIL_MCP_URL="${VEIL_MCP_URL:-http://localhost:8091/mcp}"
SSH_HOST="${CXADO_OFFLINE_SSH_HOST:-}"
SSH_PORT="${CXADO_OFFLINE_SSH_PORT:-22}"
NS_APP="${CXADO_APP_NS:-cxado-app}"
LOG_DIR="${ROOT}/deploy_logs/k3s-baseline"
STAMP="$(date +%Y%m%d-%H%M%S)"
LOG_FILE="${LOG_DIR}/veil-mcp-smoke-${STAMP}.log"
PY_SCRIPT="${ROOT}/projects/egregore/scripts/smoke_veil_mcp.py"

mkdir -p "${LOG_DIR}"

fail=0
pass() { printf 'OK   %s\n' "$1" | tee -a "${LOG_FILE}"; }
bad() { printf 'FAIL %s\n' "$1" | tee -a "${LOG_FILE}"; fail=1; }

kubectl_cmd() {
  if [[ -n "${SSH_HOST}" ]]; then
    ssh -p "${SSH_PORT}" "${SSH_HOST}" "KUBECONFIG=/home/bbv/.kube/config k3s kubectl $*"
  else
    kubectl "$@"
  fi
}

echo "[smoke] veil-mcp url=${VEIL_MCP_URL}" | tee "${LOG_FILE}"

if [[ -n "${SSH_HOST}" ]] && [[ "${VEIL_MCP_URL}" == http://localhost* ]]; then
  VEIL_MCP_URL="http://veil-veil-mcp.veil.svc.cluster.local:8091/mcp"
  echo "[smoke] k3s mode: ${VEIL_MCP_URL}" | tee -a "${LOG_FILE}"
fi

if [[ -n "${SSH_HOST}" ]]; then
  if kubectl_cmd -n "${NS_APP}" get deploy egregore-worker >/dev/null 2>&1; then
    if kubectl_cmd -n "${NS_APP}" exec -i deploy/egregore-worker -- /app/.venv/bin/python - "${VEIL_MCP_URL}" \
      < "${PY_SCRIPT}" >>"${LOG_FILE}" 2>&1; then
      pass "veil-mcp chain via egregore-worker"
    else
      bad "veil-mcp chain via egregore-worker (see ${LOG_FILE})"
    fi
  else
    bad "egregore-worker deploy not found for k3s smoke"
  fi
else
  PYTHON="${ROOT}/projects/egregore/.venv/bin/python"
  [[ -x "${PYTHON}" ]] || PYTHON=python3
  if "${PYTHON}" "${PY_SCRIPT}" "${VEIL_MCP_URL}" >>"${LOG_FILE}" 2>&1; then
    pass "veil-mcp chain local"
  else
    bad "veil-mcp chain local (see ${LOG_FILE})"
  fi
fi

if [[ "${fail}" -ne 0 ]]; then
  exit 1
fi
