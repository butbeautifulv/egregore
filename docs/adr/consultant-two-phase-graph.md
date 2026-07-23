# ADR: Consultant two-phase LangGraph

**Status:** Accepted (2026-07-22)

## Context

Consultant advisory jobs failed with `GRAPH_RECURSION_LIMIT` because a single ReAct agent
combined **tools** and **structured output** (`response_format=ConsultantFinding`). After the
tool ladder blocked further calls, the model kept requesting tools instead of emitting JSON.

Mitigations that were rejected:

- Second `arun` emit-only phase (race with streaming, doubles cost)
- Bumping `recursion_limit` to 50 (masks loop, does not fix architecture)
- Advisory `if` before planner LLM without a strategy abstraction

## Decision

1. **Consultant graph** (`cys_core/runtime/consultant_graph.py`):
   - `research` node: tools on, no `response_format`
   - `synthesize` node: `tools=[]`, `response_format=ConsultantFinding`, context from tool outputs
   - Conditional edge: `consultant_ladder_complete(job_id)` OR outer step cap
   - Feature flag: `CONSULTANT_TWO_PHASE_GRAPH` (default `false`)

2. **Planner routing** (`planner_strategy.py`):
   - `DeterministicAdvisoryPlannerStrategy` for advisory goals → consultant-only plan, no planner LLM
   - `PlannerRouter` delegates to LLM strategy for incident/complex goals

3. **Failure taxonomy**: `recursion_limit_exhausted` maps to `LLM_ERROR`, not `TIMEOUT`.

## Consequences

- soc/intel/hunter personas unchanged (single-phase ReAct as before)
- Dispatcher/worker copies synced for shared `cys_core` modules
- Enable `CONSULTANT_TWO_PHASE_GRAPH=true` in dev after `tests/runtime/test_consultant_graph.py` is green

## Verification

```bash
cd backend/agent-runtime
uv run pytest tests/runtime/test_consultant_graph.py \
  tests/worker/test_consultant_tool_ladder.py \
  tests/application/test_catalog_planner_strategy.py -q
```
