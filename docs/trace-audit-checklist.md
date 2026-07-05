# Egregore trace audit checklist

Manual smoke after enabling composite tracing (`OTEL_ENABLED=true`, Langfuse keys in `.env`).

## Preconditions

1. `make cxado-up-minimal` or full observability profile with Tempo
2. `OTEL_ENABLED=true`, `OBS_TRACE_BACKEND=langfuse` (resolves to composite when OTEL on)
3. Matching Langfuse keys in `projects/egregore/.env`

## Engagement path

1. POST `/events` or start engagement via API
2. Wait for worker to complete a job
3. **Langfuse:** session = `engagement_id`; spans include `ingress.route_and_enqueue`, `worker.process_job`, `worker.agent.run`
4. **Grafana/Tempo:** `{resource.service.name="egregore-api"}` and `{resource.service.name="egregore-worker"}` show linked spans when propagation enabled

## Control plane

1. Run critic/coordinator daemons with a finding on the bus
2. Expect `control.critic.process` or `control.coordinator.narrate` in Langfuse

## Regression checks

- Single `worker.process_job` root per job (no duplicate from orchestrator)
- Logs include `correlation_id` and OTEL `trace_id` when OTEL enabled
