# K3s offline deploy — dispatcher split

SSOT for egregore on P30 offline k3s (`192.168.0.133`). Meta-repo scripts build images via Kaniko and helm-upgrade into `cxado-app`.

## Topology

| Component | Deployment | Image (Nexus) |
|-----------|------------|---------------|
| API | `egregore-api` | `cxado-docker/egregore-api` |
| Dispatcher | `egregore-dispatcher` | `cxado-docker/egregore-dispatcher` |
| Agent execution | Batch `Job` pods | `cxado-docker/egregore-agent-runtime` |
| Tool gateway | `tool-gateway` | `cxado-docker/egregore-tool-gateway` |
| UI | `egregore-ui` | `cxado-docker/egregore-ui` |
| Worker monolith | `egregore-worker` **replicas: 0** | (rollback only) |

**UI URL:** `https://192.168.0.133:30300`

## Daily deploy

```bash
# Commit projects/egregore first (Kaniko dirty-tree guard)
TAG="$(git -C projects/egregore rev-parse --short HEAD)"
./scripts/k8s/cxado-nexus-deploy.sh --build --tag "${TAG}"
./scripts/k8s/obs-deploy-dashboards.sh
./scripts/k8s/e2e-verify-egregore.sh
```

## Env (cluster)

| Variable | Offline value | Notes |
|----------|---------------|-------|
| `EXECUTION_BACKEND` | `k8s` | Dispatcher creates Batch Jobs |
| `K8S_WORKER_IMAGE` | `…/egregore-agent-runtime:${TAG}` | From Helm `agentRuntime.image` |
| `CONTROL_MODE` | `daemon` | On dispatcher Deployment |
| `TOOL_HITL_MODE` | `enforce` | Inline chat approval required |
| `STREAM_AGENT_OUTPUT` | `true` | SSE deltas + finding snapshots |
| `STREAM_AGENT_TOKEN_STREAMING` | `true` | Token-by-token assistant text |
| `USE_TOOL_GATEWAY` | `true` | Agent-runtime Jobs call in-cluster gateway |

Job pods inherit `egregore-env` ConfigMap + `egregore-secrets` via `envFrom` (`k8s_backend.py`).

**UI build:** `NEXT_PUBLIC_EGRESS_SSE=1`; keep `NEXT_PUBLIC_HITL_CHAT_AUTO_APPROVE` **unset** on cluster (enforce ≠ auto-approve).

## Verify

```bash
./scripts/k8s/verify-egregore-rollout.sh
curl -sk https://192.168.0.133:30300/api/egregore/health   # stream_agent_output: true
kubectl -n cxado-app get deploy egregore-api,egregore-dispatcher,tool-gateway,egregore-ui
kubectl -n cxado-app get jobs -l app=egregore-agent-runtime
```

## Rollback

1. Set `worker.replicas: 2`, `dispatcher.enabled: false`, `env.executionBackend: inprocess` in `values-egregore-offline.yaml`.
2. `helm upgrade` with previous image tag: `./scripts/k8s/cxado-nexus-deploy.sh --skip-build --tag <prev>`.
3. Temporary HITL demo: `env.toolHitlMode: shadow` (document reason in change log).

## Related

- Meta loop: [`docs/deploy/nexus-egregore-loop.md`](../../../../docs/deploy/nexus-egregore-loop.md)
- Offline baseline: [`docs/deploy/k3s-offline-baseline.md`](../../../../docs/deploy/k3s-offline-baseline.md)
- Local dev: [`DEVELOPMENT.md`](../DEVELOPMENT.md) §6–7
- Backlog: [`MSP_BACKLOG.md`](../MSP_BACKLOG.md) §68
