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

## SIEM MCP (SOC)

1. `SIEM_MCP_ENABLED=true`, `make cxado-up-siem-mcp`
2. Start SOC worker on an engagement with SIEM context
3. **Langfuse:** filter `investigate_incident` or metadata `source:siem-mcp`
4. **Prometheus:** `cys_tool_invocations_total{tool="investigate_incident"}` > 0
5. **Kafka** (if `USE_KAFKA=true`): topic `audit.tool.invocations` contains `investigate_incident`

## Nessus MCP (vulnerability inventory)

1. `NESSUS_MCP_ENABLED=true`, `make cxado-up-tenable-mcp`
2. Start hunter or network worker on engagement with host/IP context
3. **Langfuse:** filter `sync_scan_inventory` or metadata `source:nessus-mcp`
4. **Prometheus:** `cys_tool_invocations_total{tool="sync_scan_inventory"}` > 0
5. **Kafka** (if `USE_KAFKA=true`): topic `audit.tool.invocations` contains a nessus tool name
6. Smoke: `make cxado-smoke-tenable-mcp`

## Veil MCP (CTI / playbooks)

1. `VEIL_MCP_ENABLED=true`, `make cxado-up-veil`
2. Start intel or SOC worker on engagement with IOC or MITRE technique context
3. **Langfuse:** filter `playbook_search` or `ti_search_in_category`, metadata `source:veil-mcp`
4. **Prometheus:** `cys_tool_invocations_total{tool="playbook_search"}` > 0
5. **Kafka** (if `USE_KAFKA=true`): topic `audit.tool.invocations` contains a veil tool name
6. Smoke: `projects/egregore/scripts/smoke_veil_mcp.sh`
