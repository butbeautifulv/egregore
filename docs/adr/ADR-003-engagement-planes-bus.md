# ADR-003: Engagement planes, bus fabric, egress

## Status

Accepted — Implemented

## Context

Egregore mixed ingress, orchestration, execution, and control in a single API/worker process.
`manual.investigation` was a SOC-specific special case. `/runs` invoked `AgentRuntime` in-process,
bypassing queue and sandbox. SecureAgentBus delivered only to critic/coordinator subscribers.

## Decision

Five logical roles plus horizontal bus fabric:

1. **Ingress** — accept `EngagementRequest` (`POST /v1/engagements`); legacy `/events` and `/runs` shims.
2. **Orchestration** — routing, queue, `BusIngressRouter`, engagement lifecycle.
3. **Execution** — sandbox workload + `RunKernelPort` + `AgentRuntime` (worker only in prod).
4. **Control** — symmetric `CriticHandler` / `CoordinatorHandler`; bus-only revision enqueue.
5. **Egress** — `EngagementEgressPort`; SSE + status snapshots for UI.

`SecureAgentBus` is not a plane; it is transport + policy between agents.

## Implementation notes

- `manual.investigation` → `StartEngagement` shim on `POST /events` (deprecated).
- `Container.get_start_engagement()` is the single composition-root factory for ingress.
- `EngagementStateStore` is primary; investigation store adapter dual-writes during migration.
- Egress is the sole outbound path for engagement status (no dual-write).
- Bus revisions and findings use `publish_delivery` + `BusIngressRouter` only.
- `/runs` routes through engagements; `ManageRun` removed from API.
- UI uses `/v1/engagements` + optional SSE (`NEXT_PUBLIC_EGRESS_SSE=1`).

## Bus message types

`finding`, `delegate`, `revision`, `escalation`, `control`, `report`

## Threat model

Production: no `AgentRuntime.arun` in `interfaces/api/`.
Interactive work flows through conductor job + egress stream.
