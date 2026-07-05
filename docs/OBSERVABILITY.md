# Observability — local and k3s

## Span catalog

| Span | Layer | Trigger |
|------|-------|---------|
| `api.request` | interfaces | HTTP middleware |
| `ingress.route_and_enqueue` | application | POST /events |
| `ingress.dispatch` | application | router / dispatch |
| `ingress.kafka.consume` | interfaces | router consumer |
| `engagement.plan` | application | meta-LLM planner |
| `engagement.start` | application | start engagement |
| `worker.dequeue` | interfaces | worker orchestrator |
| `worker.process_job` | application | RunWorkerJob |
| `worker.sandbox.create` / `worker.sandbox.destroy` | application | RunWorkerJob |
| `worker.agent.run` | application | RunWorkerJob |
| `tool.invoke` | application | InvokeTool |
| `control.critic.process` | application | ProcessFindingCritic |
| `control.coordinator.narrate` | application | NarrateInvestigation |
| `bus.consume` / `bus.publish` | infrastructure | agent bus |
| `run.step` | application | RunStep |
| `run.trace_critic` | application | EvaluateTraceCritic |

## Trace backends matrix

| `OTEL_ENABLED` | `OBS_TRACE_BACKEND` | Langfuse | Tempo/Grafana |
|----------------|---------------------|----------|---------------|
| `false` | `langfuse` | yes | no |
| `true` | `langfuse` | yes (composite) | yes |
| `true` | `otel` | no | yes |
| `true` | `composite` | yes | yes |
| any | `noop` | no | no |

Langfuse = LLM/engagement drill-down. Tempo = SRE/infra view (full observability profile).

Manual audit: [trace-audit-checklist.md](trace-audit-checklist.md)

## Trace path matrix

| Path | Trace backend | Notes |
|------|---------------|-------|
| CLI `egregore agent` | Langfuse | `egregore-agent-{persona}` |
| API ingest → worker | Langfuse + Prometheus | worker spans `worker.process_job`; tags `persona:`, `job:`, `engagement:` |
| API advisory fast-path | Prometheus only | No LLM trace when planner short-circuits |
| UI → API proxy | Same as API | `EGREGORE_API_UPSTREAM` for host dev |
| Tool calls (Veil MCP) | Langfuse observations | type TOOL/SPAN when gateway enabled |
| Worker OTEL | Tempo (full profile) | `OTEL_ENABLED=true` — optional; Langfuse spans work with `OTEL_ENABLED=false` |

## Local stack (`make cxado-up-minimal`)

- Langfuse: http://localhost:3001
- Grafana: http://localhost:3002 (compose datasources → `prometheus:9090`)
- Prometheus: http://localhost:9091/targets — scrapes `host.docker.internal:8080`
- Validate: `make cxado-validate-grafana`

Lite/minimal: **Loki/Tempo panels empty** — expected.

### Langfuse keys after bootstrap

`make cxado-up-minimal` prints Langfuse init keys from `deploy/langfuse/.env` (`LANGFUSE_INIT_PROJECT_*`).
Copy the matching `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` into `projects/egregore/.env` so API and workers
use the same project as the Langfuse UI. Mismatched keys (e.g. `pk-lf-egregore-dev-local` vs bootstrap `pk-lf-dev-public`)
produce empty trace lists.

Worker traces group by **session** = `engagement_id` (`langfuse_session_id` on worker spans and LLM CallbackHandler metadata).

## Tool tracing checklist

1. `VEIL_MCP_ENABLED=true`, veil-mcp up (`make cxado-up-veil`)
2. Run consultant with playbook tool
3. Langfuse → filter by engagement ID or tags `engagement:{id}`, `persona:{name}`
4. Grafana → Egregore / SGR dashboards when metrics exist

## k3s (when cluster available)

- Grafana datasources use `*.cxado-obs.svc.cluster.local`
- Deploy gates: `scripts/k8s/e2e-verify-egregore.sh`, `deploy_logs/trace_audit_*.md`
