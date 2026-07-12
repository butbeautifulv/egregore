# ADR-007: Conductor vs meta-planner orchestration

## Status

Accepted

## Context

Egregore has two orchestration mechanisms:

- **Meta-planner** (`CatalogPlannerStrategy`) — batch planning for work orders; enqueues specialist workers from a static plan.
- **Conductor** — dynamic meta-worker with `spawn_worker` for follow-up reinvestigation and interactive orchestration.

`planner` persona AGENT.md already marks interactive deprecation in favor of conductor.

## Decision

| Entry path | Orchestrator | Control plane |
|------------|--------------|---------------|
| Work order `intent_mode=qa` | `consultant` (`initial_qa`) | off |
| Work order `intent_mode=plan` | meta-planner → specialists → synthesis | gate_only |
| Follow-up `qa` | `consultant` | off |
| Follow-up `orchestrate` | `conductor` | trace critic on steps |
| Follow-up `plan` | meta-planner re-run | gate_only |

Batch engagement planning remains on meta-planner. Interactive reinvestigation standardizes on conductor.

## Deprecation

- `planner` as interactive session driver: deprecated; target removal after conductor UI parity.
- `CRITIC_USE_LLM_JUDGE` in-app path: removed; use Langfuse platform eval + runtime heuristics.

## References

- ADR-006 (control plane roles)
- [`agents/planner/AGENT.md`](../../agents/planner/AGENT.md)
