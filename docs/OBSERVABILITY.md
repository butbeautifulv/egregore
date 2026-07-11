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
| `worker.process_job` | application | RunWorkerJob (orchestrator dequeue is not traced — idle polls every 2s) |
| `worker.sandbox.create` / `worker.sandbox.destroy` | application | RunWorkerJob |
| `worker.agent.run` | application | RunWorkerJob |
| `tool.invoke` | application | InvokeTool |
| `control.critic.process` | application | ProcessFindingCritic |
| `control.coordinator.narrate` | application | NarrateInvestigation |
| `bus.consume` / `bus.publish` | infrastructure | agent bus |
| `run.step` | application | RunStep |
| `run.trace_critic` | application | EvaluateTraceCritic |
| `follow_up.enqueue` | application | EnqueueFollowUp |
| `follow_up.plan` | application | PlanFollowUpRunner |
| `planning.catalog` | application | CatalogPlannerStrategy |
| `worker.result_validate` | application | WorkerResultValidator |

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

Worker traces group by **session** = `engagement_id` (`langfuse_session_id` on worker spans and LLM CallbackHandler metadata). LLM traces also carry tag `engagement:{engagement_id}`.

**k3s offline UI:** Langfuse project is `egregore-dev` (not `default`). Open traces via ui-minimal «Open in Langfuse» or filter `engagement:{id}` at `https://{node}:30001`.

## Tool tracing checklist

1. `VEIL_MCP_ENABLED=true`, veil-mcp up (`make cxado-up-veil`)
2. Run consultant with playbook tool
3. Langfuse → filter by engagement ID or tags `engagement:{id}`, `persona:{name}`
4. Grafana → Egregore / SGR dashboards when metrics exist

## k3s (when cluster available)

- Grafana datasources use `*.cxado-obs.svc.cluster.local`
- Deploy gates: `scripts/k8s/e2e-verify-egregore.sh`, `deploy_logs/trace_audit_*.md`
- **Worker metrics (Phase 1):** each `egregore-worker` pod exposes `http://<pod-ip>:8081/metrics` and `/health`. Prometheus job `egregore-worker` uses kubernetes pod SD (see [egregore-worker-metrics-adr.md](../../../docs/observability/egregore-worker-metrics-adr.md)). Worker job/tool/token panels in Grafana filter `job="egregore-worker"`; API ingress gauges use `job="egregore-api"`.
- Verify: `./scripts/k8s/smoke-test-egregore-obs.sh` checks worker annotations, `/health`, and `up{job="egregore-worker"}`.

## Worker job timeout runbook (5 min)

When a persona shows `worker_job_timeout` in UI or `job_finished` events:

1. **Engagement API** — `GET /v1/engagements/{id}` → `failed_personas`; `GET /v1/engagements/{id}/events` → `error=worker_job_timeout`.
2. **Langfuse** — session = `engagement_id`; open `worker.process_job` / `worker.agent.run` for the failed persona. Check duration (~360s offline) and count of `tool.invoke` children.
3. **Worker logs** — filter `correlation_id={engagement_id}` and events `worker job timed out`, `worker_siem_finding_nudge`, `tool_ladder_veil_blocked`, `worker_timeout_salvaged`.
4. **Prometheus** — `cys_worker_job_timeout_total{persona="soc|intel"}`; `cys_worker_job_duration_seconds` (buckets include 420s, 600s); `cys_tool_invocations_total` by tool name.
5. **Mitigations in code** — triage personas use `TRIAGE_RECURSION_LIMIT=22`, `max_tool_calls=6`, tool dedup middleware, tool ladder, soft timeout salvage at 90% wall clock, and partial salvage from cached tool previews (timeout, budget, or recursion limit).

If Prometheus multiproc fails with `UnicodeDecodeError`, clear stale files on the node: `sudo rm /var/lib/cxado/prom-multiproc/*.db`.

## Sparse SIEM vs hallucination runbook

When SOC or consultant findings mention specific processes, pipes, or credential-dumping tools but SIEM/KATA telemetry is thin:

1. **Finding fields** — check `telemetry_level` (`sparse` / `metadata_only`), `data_gaps[]`, and `evidence[].obs_id` on the SocFinding.
2. **Worker logs** — `worker_grounding_rejected` with `ungrounded_claims` (structural gate, not token blacklist).
3. **Tool output** — `investigate_incident` returns `evidence_manifest` with `required_external_sources` (e.g. `kata_taa_console`) and `max_confidence`.
4. **Expected behavior** — sparse KATA TAA alerts: host + rule + gaps, confidence ≤ 0.5, remediation pointing to KATA console — not invented cmdline/PID/pipe names.
5. **Critic** — `critic_verdict` log includes `issues_detected` when structural validation fails post-publish.

Distinguish from timeout issues: grounding failures raise `ungrounded_finding:*` before publish; timeouts use `worker_job_timeout` runbook above.

## Worker failure taxonomy (Phase 3)

Terminal worker failures emit structured logs and metrics:

- **Metric:** `cys_worker_job_failures_total{persona,reason}` on `job="egregore-worker"`
- **Log:** `worker_job_failed` with fields `correlation_id`, `engagement_id`, `persona`, `job_id`, `reason`, `error_class`, `error`
- **Egress:** `job_finished` includes `reason` (UI may still parse legacy `error` prefixes)

Primary drill-down:

```promql
topk(10, sum(increase(cys_worker_job_failures_total{job="egregore-worker"}[1h])) by (reason))
```

Full mapping and runbooks: [worker-failure-taxonomy.md](../../../docs/observability/worker-failure-taxonomy.md).

## Operator smoke (work orders)

```bash
BASE="http://127.0.0.1:8080"
curl -sf "$BASE/health"
curl -sf -X POST "$BASE/v1/work-orders" \
  -H 'Content-Type: application/json' \
  -d '{"goal":"Smoke test","tenant_id":"default"}'
# closed WO follow-up:
curl -sf -X POST "$BASE/v1/work-orders/{id}/follow-ups" \
  -H 'Content-Type: application/json' \
  -d '{"message":"What was the main finding?","tenant_id":"default"}'
```

SSE: `GET /v1/work-orders/{id}/events?tenant_id=default` — watch for `follow_up_*` events during follow-up flows.
