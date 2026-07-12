# ADR-006: Control plane roles and quality layers

## Status

Accepted — Implementing

## Context

Egregore uses several names that overlap in meaning:

- **coordinator** was described as an "orchestrator" in persona yaml but only narrates worker activity.
- **critic** was documented as a rich LLM judge but runs heuristics on the bus in-process.
- **conductor** is the real dynamic meta-worker (`spawn_worker`) but is rarely the default entry path.
- **Langfuse LLM-as-judge** exists as async platform eval jobs; in-app `LangfuseJudgeBackend` is a stub.

Operators see JSON from critic/coordinator on every worker finding, which obscures the real deliverable (synthesis / advisory outcome).

## Decision

### Role naming (canonical)

| Persona / component | Role | Operator-visible? |
|---------------------|------|-------------------|
| **Meta-planner** (`CatalogPlannerStrategy`) | Batch engagement planning | Plan card only |
| **conductor** | Dynamic orchestration (`spawn_worker`, follow-up reinvestigate) | When orchestrate mode |
| **Synthesis worker** | Primary multi-agent deliverable | **Yes** — `final_report` / `OperatorOutcome` |
| **coordinator** | Engagement progress narrator | Progress strip only (not per-finding chat) |
| **critic** | Runtime quality gate (revision / cap) | Only on fail or revision |
| **Langfuse eval** | Offline LLM quality on GENERATION spans | Observability UI only |

**coordinator is not an orchestrator.** **conductor** and **meta-planner** orchestrate.

### Quality layers (do not merge)

1. **Runtime gate** — `ProcessFindingCritic` heuristics + evidence gaps; may enqueue revision.
2. **Trace critic** — `EvaluateTraceCritic` on conductor steps when `TRACE_CRITIC_ENABLED`.
3. **Platform eval** — Langfuse Helpfulness/Hallucination jobs on traces (async).

Do not enable `CRITIC_USE_LLM_JUDGE` expecting in-app LLM judge; use Langfuse eval for LLM quality monitoring.

### Profile-aware control plane

`control_plane_mode` on profile packs:

- `off` — advisory / `initial_qa` (no critic/coordinator bus)
- `gate_only` — critic revision, no coordinator chat
- `full` — critic + coordinator status events (legacy incident flows)

### Operator deliverable

Canonical operator artifact is **`OperatorOutcome`** in `final_report`. Specialist `findings_summary` entries are internal (`visibility: internal`) unless explicitly operator-facing.

## Consequences

- UI hides critic pass events and collapses specialist findings.
- Persona yaml descriptions aligned with runtime behavior.
- Revision feedback carries human-readable `issues_detected`, not opaque tokens.

## References

- ADR-003 (engagement planes, bus)
- [`operator-console-contract.md`](../operator-console-contract.md)
- Control plane cleanup plan (P0–P5)
