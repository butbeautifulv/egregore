# Schema-Guided Reasoning (SGR) in Egregore

## ADR: Pattern port from reference

**Status:** accepted  
**North star:** mandatory per-step schema-guided reasoning for small models, without importing `sgr-agent-core` at runtime.

Egregore adapts patterns from [`shared/references/sgr-agent-core-main`](../../../shared/references/sgr-agent-core-main) (read-only). Production code must **not** import that package.

### Decision

- **Pattern port** into LangChain middleware + domain schemas (not pip dependency, not sidecar).
- Opt-in via `ProfilePolicyPayload.sgr`, `agent.yaml` `reasoning_mode`, and `USE_SGR_REASONING`.
- Rollout order: workers → conductor → planner.

## SGR ↔ Egregore mapping

| SGR reference | Egregore |
|---------------|----------|
| `ReasoningTool` | `SchemaGuidedReasoningStep` + `reasoning_step` tool |
| `SGRToolCallingAgent` | `sgr_hybrid`: `REASONING_MODEL` then main model |
| `IronAgent` | `sgr_iron`: `ToolInstantiator` + text JSON |
| `GeneratePlanTool` | `GeneratePlanPayload` in `plan_investigation` |
| `AdaptPlanTool` | `AdaptPlanPayload` in PLAN mode |
| `BaseAgent` two-phase loop | `SchemaGuidedReasoningMiddleware` |
| `NextStepToolsBuilder` | **Deferred P4+** — optional extension; not required for hybrid/iron gate. See [NextStepTools (deferred)](#nextsteptools-deferred) |

## NextStepTools (deferred)

`NextStepToolsBuilder` from the SGR reference (dynamic per-turn tool schema narrowing) is **not** in P4 scope.
Hybrid and iron paths use full allowlisted tools + `reasoning_step` gate. A future P9+ extension may add
per-turn tool subsets without changing the middleware order above.

## Middleware stack order

```
PromptContext → Memory → ContextSummary → Scope → ToolCoercion → Security
→ HITL → SchemaGuidedReasoning → SgrOneTool
```

SGR runs **after** Security/HITL so policy gates still apply. `reasoning_step` is LOW risk and auto-approved.

## Policy precedence

1. `ProfilePolicyPayload.sgr` (catalog)
2. `agent.yaml` `reasoning_mode`
3. `USE_SGR_REASONING` env kill-switch
4. Default: off

## Test strategy

- **Gate tests:** middleware blocks action tools until `reasoning_step` (`tests/middleware/test_sgr_reasoning_middleware.py`).
- **Mock LLM:** two-phase hybrid with fake `ModelConnector`.
- **Instantiator:** JSON parse retry paths (`tests/application/test_sgr_tool_instantiator.py`).
- **A/B metrics:** compare worker tool error rate with `sgr.enabled` on `gaia-bench` profile.

## Small-model playbook

| Model class | Recommended mode |
|-------------|------------------|
| Cloud mini (gpt-4.1-mini, claude-haiku) | `sgr_hybrid` + `REASONING_MODEL` |
| Local 7B–14B without tool calling | `sgr_iron` |
| Large models with native FC | `off` or `sgr_hybrid` for auditability |

Settings: `USE_SGR_REASONING`, `SGR_DEFAULT_MODE`, `SGR_IRON_MAX_RETRIES`.

## CI guard

```bash
# Must return empty — no runtime imports from reference tree
rg 'from sgr_agent_core|import sgr_agent_core' projects/egregore/cys_core projects/egregore/bootstrap
```
