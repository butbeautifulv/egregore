# TraceEvent taxonomy (draft, Stream D0)

Unified trace schema for RunKernel (D2). Events are append-only within a run trajectory.

## Core types

| Type | Fields | Source |
|------|--------|--------|
| `model_call` | model, tokens_in/out, latency_ms, cost_usd | LLM middleware |
| `tool_call` | tool, args_digest, success, latency_ms | Tool gateway / runtime |
| `memory_read` | tenant, investigation_id, entries | MemoryContextMiddleware |
| `memory_write` | tenant, memory_type, size | RunWorkerJob / RunStep |
| `eval` | suite, metric, score | Trace critic / GAIA |
| `policy` | rule, decision, profile_id | SecurityMiddleware, policy resolver |
| `bus` | channel, recipient, message_type | SecureAgentBus transport |

## Correlation

All events carry:

- `run_id` / `job_id`
- `correlation_id` (investigation)
- `persona`
- `profile_id`

## Storage

- Langfuse spans (dev/prod optional)
- Prometheus counters (aggregates)
- Future: `AgentTrajectory` domain model (D2)
