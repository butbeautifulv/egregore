# Platform inventory — wave D0

Consolidated inventories for Stream D phase 0 (master-p0-01 … p0-07).

## Runtime (`cys_core/runtime/agent.py`)

| Responsibility | Owner |
|----------------|-------|
| Agent graph construction | `AgentRuntime.create` / `create_agent` |
| Middleware ordering | `_build_middleware` |
| Persistence (sync/async) | `_sync_persistence` / `_async_persistence` |
| LLM callbacks | `model_connector.callbacks()` |

**Middleware order (worker/interactive):**

1. `PromptContextMiddleware`
2. `MemoryContextMiddleware` (when investigation_id set)
3. `ContextSummaryMiddleware` (when enabled)
4. `ScopeMiddleware` → `ToolCoercionMiddleware` → `SecurityMiddleware`
5. `HumanInTheLoopMiddleware` (per-agent hitl_tools)
6. SGR: `SchemaGuidedReasoningMiddleware` + `SgrOneToolMiddleware` **or** `OneToolPerTurnMiddleware`

## Orchestration paths

| Path | Entry | Use case |
|------|-------|----------|
| Interactive | `RunStep` / `ManageRun` | API `/runs`, conductor flows |
| Worker | `RunWorkerJob` via `WorkerOrchestrator` | Kafka/Redis job queue |
| Ingress async | `complete_manual_investigation_planning` | HTTP 202 planner |

Shared: `AgentRuntime.arun`, budget via `JobBudgetTracker`, memory read/write services, tool gateway resolution.

## Tools (`cys_core/registry/tools.py`, MCP)

| Class | Examples |
|-------|----------|
| Real | SIEM, Veil/Veneno MCP, gateway tools |
| Simulated | sandbox-scoped stubs in tests |
| Stub | unconfigured external integrations |
| Disabled | `enabled: false` in tool catalog |

## Memory / RAG

- Read: `MemoryContextMiddleware`, investigation store
- Write: `RunWorkerJob` terminal hooks, `record_memory_write` metric
- Gap: provenance fields on memory entries (D2 kernel target)

## Eval / GAIA

- GAIA pipeline: `cys_core/benchmarks/gaia_pipeline.py`
- Trace critic: `evaluate_trace_critic` use case
- Stubs: escalation publish mocks in tests

## Policy

- Profile policy: `ProfilePolicyLoader` / Postgres catalog
- Fail-open: infrastructure fallback → in-memory queue/bus/rate limit
- Metric: `cys_infrastructure_fallback_total`, `cys_persistence_fallback_total`

## SOC literals (shrink list)

| Location | Literal |
|----------|---------|
| `DEFAULT_PROFILE_ID` | `cybersec-soc` |
| `bootstrap/catalog_loader` | cybersec profile seed |
| `agents/plans/incident-triage.yaml` | default SOC routing |

Target: explicit `profile_id` on all ingress events; product packs in `bootstrap/product_packs.py`.
