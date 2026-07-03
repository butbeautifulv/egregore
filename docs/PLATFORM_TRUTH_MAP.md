# Platform Truth Map (P0)

This document is a **baseline inventory** for the Egregore “general agent platform” master plan.
It is intentionally **descriptive only** (no runtime changes).

## P0.1 Inventory: AgentRuntime responsibilities + middleware order

Primary entrypoint:

- `cys_core/runtime/agent.py` → `AgentRuntime`

High-level responsibilities currently owned by `AgentRuntime`:

- Agent definition lookup (`AgentRegistry`)
- Model connector selection (`ModelConnector`)
- Tool resolution (`ToolRegistry` + profile allowlist filtering)
- Middleware assembly (security, scope, HITL, memory context, SGR gates, etc.)
- Persistence/checkpointer/store wiring
- “Structured output from text” helper `_parse_json_text()` (used by worker path too)

Middleware order (from `_build_middleware()`):

1. `PromptContextMiddleware` (sanitizer + guardrails + prompt digest + ids)
2. `MemoryContextMiddleware` (only when memory reader is configured and `investigation_id` is set)
3. `ContextSummaryMiddleware` (optional; when enabled by settings)
4. `ScopeMiddleware` (allowed tools from agent definition)
5. `ToolCoercionMiddleware`
6. `SecurityMiddleware`
7. `HumanInTheLoopMiddleware` (optional; when interrupt tools present)
8. `SchemaGuidedReasoningMiddleware` + `SgrOneToolMiddleware` (optional; when SGR resolved enabled)
9. else `OneToolPerTurnMiddleware` (optional; env gate)

Notes:

- SGR is currently implemented as *middleware enforcement* around a tool (`reasoning_step`).
- The master plan’s “real SGR runtime” (reason→act with `REASONING_MODEL`) is not implemented yet.

## P0.2 Inventory: orchestration paths (RunStep vs RunWorkerJob)

Interactive path:

- `cys_core/application/use_cases/run_step.py` → `RunStep`
  - Constructs/updates `RunState`
  - Applies strict-plan policy helpers (optional)
  - Runs trace critic (optional)
  - Manages work todos + attachments + reflexion store

Worker path:

- `cys_core/application/use_cases/run_worker_job.py` → `RunWorkerJob`
  - Sandbox / transport / queue integration
  - Ingress payload → investigation context → memory read/write
  - Uses `AgentRunner` (runtime) to execute persona
  - Publishes outputs/events via `SecureAgentBus`

Shared-ish concepts (but not shared models yet):

- Both paths execute agents and tools, but capture/emit outcomes differently.
- Both reference `DEFAULT_PROFILE_ID` and per-profile policies, but resolve them via different call chains.

## P0.3 Inventory: tools by category (real / simulated / stub / disabled)

Tool entrypoint:

- `cys_core/registry/tools.py`

Observed categories:

- **Gateway-backed / integration-backed (real when configured)**:
  - `web_search`, `read_document`, `search_archived_webpage`, `vision_analyze`
  - MCP-backed tools via Veil/Veneno integration (e.g. `enrich_ioc`, `run_active_scan`) when enabled
- **Backend-port backed (real when ToolBackend is configured)**:
  - `query_siem_readonly`, `rag_query`
- **Pure local helpers (real-ish)**:
  - `extract_structured_output`
  - `reasoning_step` (SGR schema recorder; see P0.1)
- **Stubs / simulated** (examples):
  - `read_repo_metadata` (always returns simulated metadata)
  - `parse_netflow` (parses heuristically; labels itself `netflow_stub`)

The current registry is a single list `_ALL_TOOLS` with mixed concerns. The master plan’s P3
proposes splitting this into “providers” + schema exporter + BFCL readiness.

## P0.4 Inventory: memory/RAG context flows + provenance gaps

Current domain models:

- `cys_core/domain/memory/models.py`:
  - `MemoryEntry` with `scope`, `content`, `memory_type`, source fields, trust score, checksum
- `cys_core/domain/rag/models.py`:
  - `RagChunk` with `acl` + `provenance`
  - `RetrievalResult` with `query`, `chunks`, `denied_count`, `fail_closed`

Current flows:

- **Worker** (`RunWorkerJob`):
  - constructs an “investigation context”
  - reads/writes investigation memory via `MemoryReadService` / `MemoryWriteService`
- **Interactive** (`AgentRuntime`):
  - optionally injects memory context via `MemoryContextMiddleware`

Provenance gaps (for RAGAS/FaithEval/FActScore):

- We have provenance at the chunk level (`DocumentProvenance`) but no unified “retrieval context”
  that can be exported as (question, answer, contexts) triples for eval tooling.
- Tracing of denied/filtered chunks is not standardized as a first-class event type.

## P0.5 Inventory: eval/judge/benchmark stubs + GAIA path

Eval-ish ports / stubs:

- `cys_core/application/ports/observability/eval_backend.py` (very small surface)
- `cys_core/domain/observability/models.py` → `EvalScore`

Trace critic (lightweight evaluation):

- `cys_core/application/use_cases/evaluate_trace_critic.py`
- `cys_core/domain/runs/trace_models.py`

Benchmarks:

- `cys_core/benchmarks/gaia_pipeline.py` (+ normalizer)

Missing (planned in P6+):

- First-class `EvalCase`, `EvalDataset`, `EvalRun`, `EvalSampleResult` models
- Artifact store + CLI runner

## P0.6 Inventory: policy fallback paths + fail-open behavior

Policy resolver:

- `cys_core/application/policy_resolver.py` → `ProfilePolicyResolver`

Current behavior:

- If a catalog policy loader exists but throws, resolver **swallows exceptions** and falls back to
  `default_profile_policy_payload()` (fail-open).
- Similarly for default personas and max spawn depth.

This is intentionally permissive today; the master plan P9 hardens this with fail-closed behavior
outside dev and adds explicit observability.

## P0.7 Inventory: SOC literals/defaults in core

Examples (non-exhaustive):

- `cys_core/domain/events/models.py` event type literal list is SOC-centric.
- `bootstrap/policy_defaults.py` names the default profile pack “Cybersec SOC”.
- `agents/manifest.yaml` is described as a “cybersecurity assessment platform”.

The master plan’s P1 introduces product packs/domain packs to move these out of core.

## P0.8 Draft: TraceEvent taxonomy (for future unified trajectory)

Target: a unified “trajectory”/trace model capturing:

- **Model events**: prompt, model name, tokens, cost, latency
- **Tool events**: tool name, args summary, result status, risk tier
- **Memory/RAG events**: retrieval query, chunk ids, provenance refs, denied counts
- **Eval events**: critic verdicts, judge scores, suite/sample identifiers
- **Policy events**: allow/deny decisions, fallbacks, risk downgrade approvals

This taxonomy is a doc-only placeholder for P2’s formal domain models (`TraceEvent`, `AgentTrajectory`).

## P0.9–P0.10 Smoke test outlines (doc-only)

Interactive smoke (outline):

1. Instantiate a simple persona with `reasoning_step` available.
2. Run one interactive turn with a safe tool call (`extract_structured_output`).
3. Assert the tool call succeeds and returns JSON.

Worker smoke (outline):

1. Route a `manual.investigation`-like event into one worker job.
2. Ensure sanitizer + guardrails run.
3. Ensure memory read/write hooks are invoked (in-memory adapter acceptable).

## P0.11 Stub tool usage metric spec (doc-only)

Goal: emit a metric when a **stub/simulated** tool is invoked so eval/ops can track reliance on stubs.

Proposed metric:

- Counter: `cys_tool_stub_invocations_total{tool="<name>", mode="<stub|simulated>"}`.

Implementation note:

- This requires `ToolRegistry` metadata (P3 “tool status model”) to classify tools.

## P0.12 Policy fallback metric spec (doc-only)

Goal: when policy resolution falls back (e.g., loader error), emit:

- Counter: `cys_policy_fallback_total{kind="<policy|personas|max_spawn_depth>", profile_id="<id>", stage="<dev|prod>"}`
- Log warning including exception type + message.

Severity guidance:

- dev: warn + metric (continue)
- non-dev: warn + metric, then fail-closed for critical loader failures (P9)

