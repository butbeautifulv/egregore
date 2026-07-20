# Microservices Split — Active Plan

> Full history, investigations, and reasoning behind every decision below live in
> [`docs/MSP_BACKLOG.md`](MSP_BACKLOG.md) (§0–§50.1). This file is the current to-do list only —
> straight to the point, no narrative. When an item below is done, move its summary to
> `MSP_BACKLOG.md` and delete it from here.

## Current state (as of 2026-07-18)

Four independent backend packages, no shared package between any of them (each carries its own
physical copy of `cys_core.domain`/`bootstrap`/generic infra — duplication is deliberate, see
`MSP_BACKLOG.md` §18):

| Package | Job | Status |
|---|---|---|
| `backend/api/` | FastAPI ingress/CRUD, event routing, HITL resume over HTTP | Deployed, wired, CI-complete |
| `backend/worker/` | Agent-execution runtime (LangChain/LangGraph) + control-plane daemons (critic/coordinator) | Deployed, wired, CI-complete |
| `backend/tool-gateway/` | PEP for sandboxed agent tool calls (async stdlib server, no FastAPI/langchain) | Deployed, wired, CI-complete |
| `backend/model-gateway/` | LLM-call chokepoint — input sanitize, system-prompt-digest check, output-leakage guard | **Built and tested, not wired into anything yet** (see §1 below) |

No `langchain`/`langgraph`/`deepagents`/`litellm` anywhere in `api`. No FastAPI anywhere in `worker`
or `tool-gateway`. `release-gate.yml` is green; `lint`/`unit-tests`/`linter-security`/CodeQL cover all
four packages, `arch-lint`/`domain-coverage`/`adversarial` cover the first three only (`model-gateway`
lacks the prerequisite files — see §1).

---

## §1 — PRIMARY GOAL: split `worker` into `dispatcher` + `agent_runtime` as separate services

**Explicit ask (2026-07-18): make dispatcher and agent_runtime separate services, not just an
internal module boundary.** This resolves `MSP_BACKLOG.md` §22.6's open question in favor of
extraction — mirroring the `tool-gateway`/`model-gateway` precedent (own `backend/` package, own
`pyproject.toml`/`uv.lock`, own CI matrix entry).

### What already exists to build on (don't rebuild these)

- **The port is already drawn and wired.** `cys_core/application/ports/agent_runner.py`'s
  `AgentRunner` Protocol is the dispatcher↔runtime seam. `WorkerOrchestrator` depends on it only
  (no concrete `AgentRuntime` import) — closed in `MSP_BACKLOG.md` §30.
- **Sandbox backends for out-of-process execution already exist and are tested**:
  `InProcessExecutionBackend`, `SubprocessExecutionBackend`, `DockerExecutionBackend`,
  `K8sExecutionBackend` (`cys_core/application/ports/execution_backend.py` + implementations). The
  out-of-process child entrypoint (`egregore run-sandboxed-job` →
  `execute_sandboxed_job()`) is real and tested, not a stub (`MSP_BACKLOG.md` §34).
- **`AgentRuntime` (`cys_core/runtime/agent.py`, 666 lines + ~10 langchain-middleware classes) is
  the one and only `AgentRunner` implementation today** — this is what becomes `agent_runtime`'s
  package content, unchanged in behavior, just relocated.

### What's actually missing

1. **Physical package split.** `backend/worker/` → `backend/dispatcher/` (queue consumption,
   budget/trust/policy resolution, `ExecutionBackend` selection — i.e. everything that's already
   framework-clean) + new `backend/agent-runtime/` (today's `cys_core/runtime/agent.py`, its
   middleware stack, `cys_core/llm/*` — carries the langchain/langgraph dependency, `dispatcher`
   never does). Not started.
2. **Wire `AgentRunner` across the new process boundary**, not just across an in-process Protocol.
   Today's subprocess/Docker/K8s backends already speak `SubprocessJobEnvelope` in/`RunResult` out —
   confirm that contract is sufficient once the two sides are genuinely separate deployables, or
   extend it. Not started.
3. **`model-gateway` needs to actually be called.** `AgentRuntime` still calls `litellm`
   in-process directly; `model-gateway` (the LLM-call chokepoint) exists, is tested, but nothing
   points at it (`MSP_BACKLOG.md` §29.4). Wiring `agent_runtime` to call out to `model-gateway`
   instead of litellm directly is part of making the split "secure by design regardless of which
   runtime is plugged in" (`MSP_BACKLOG.md` §22.8–§22.11).
4. **`ModelConnector`/`ChatModelProvider`'s return type is pinned to `langchain_core.BaseChatModel`**
   (`cys_core/application/ports/llm.py`, `cys_core/llm/protocol.py`). Blocks a genuinely
   framework-neutral second `AgentRunner` implementation (the actual point of this split — "so i can
   run grok claude etc from dispatcher if i want to switch runtime"). Needs a framework-neutral
   model-handle type at this boundary. Not started.
5. **HITL pause/resume across the boundary.** Today's mechanism is `langgraph.interrupt()` +
   checkpointer — fundamentally in-process-shaped. A real design already exists
   (`MSP_BACKLOG.md` §35: refuse-then-retry with an `approval_id` token, reusing
   `ResumeHitlJob`'s existing anti-tampering pattern) but is **not implemented** — flagged as
   high-risk to ship untested against a live security boundary without an integration environment.
   This blocks HITL from working correctly once `agent_runtime` is a separate process.
6. **Sandbox isolation beyond K8s/Docker** (gVisor `runtimeClassName`, Kata Containers) — documented
   only (`MSP_BACKLOG.md` §22.5), zero code. Likely reduces to a `runtimeClassName` field on
   `K8sExecutionBackend` rather than new backend classes, but unvalidated against a real cluster.
7. **CI/deploy for the new `agent-runtime` package** — no Dockerfile, no compose/Helm entry, no
   `release-gate.yml` matrix entry. Same bootstrap work `tool-gateway`/`model-gateway` each needed.

### Suggested phasing (small diffs, each independently verifiable — mirrors `MSP_BACKLOG.md` §7's
### original phasing discipline)

1. Extract `backend/agent-runtime/` as a package (copy `cys_core/runtime/agent.py` + middleware +
   `cys_core/llm/*`, own `pyproject.toml`), no behavior change, still called in-process via the
   existing `AgentRunner` Protocol from `backend/worker/` (temporary — validates the extraction
   before touching process boundaries).
2. Rename/reshape `backend/worker/` → `backend/dispatcher/`, stripped of `cys_core/runtime/agent.py`
   and the middleware stack (now only in `agent-runtime`).
3. Wire `dispatcher` → `agent-runtime` across a real process boundary using the existing
   subprocess/Docker/K8s `ExecutionBackend`s — validate the `SubprocessJobEnvelope`/`RunResult`
   contract holds for two genuinely separate deployables, not just separate in-process modules.
4. Wire `agent-runtime` → `model-gateway` for LLM calls (closes item 3 above).
5. Resolve the `ModelConnector` `BaseChatModel` pinning (closes item 4) — needed before a second
   `AgentRunner` implementation is worth building.
6. Implement the HITL pause/resume redesign (closes item 5) — do this before relying on the split
   in production with HITL-gated personas.
7. CI/deploy bootstrap for `agent-runtime` (closes item 7).
8. gVisor/Kata (item 6) — only after the above is stable; start with the `runtimeClassName` field
   approach on `K8sExecutionBackend`, validate against a real cluster before assuming a new backend
   class is needed.

Full reasoning, the original ask verbatim, and every open sub-question: `MSP_BACKLOG.md` §22, §30,
§34, §35.

---

## §2 — Everything else not done, by theme

Each item: one line, pointer to full reasoning. None of these are blocked on §1 — independent work.

### Core architecture / domain
- **Core still hardcodes SOC domain in 6 places** (`EventType`/`WorkerAgentName` closed `Literal`s,
  11 concrete `Finding` subclasses, `ESCALATION_ONLY_PATHS`/`READ_ONLY_TOOLS`, unconditional
  `ToolRegistry` SIEM/Veil/Nessus registration, `DEFAULT_PROFILE_ID`). Re-verified current
  2026-07-18. Large cross-cutting refactor across all packages' domain layers, target model already
  written. Acceptance test: build a toy non-SOC pack touching zero `cys_core/domain` files.
  `MSP_BACKLOG.md` §8, §24.1.
- **Semantic/long-term agent memory tier doesn't exist** — `memory_type` schema has `lesson`/
  `preference` slots, nothing ever writes them. No cross-engagement persona+tenant memory query.
  `MSP_BACKLOG.md` §9.

### Job resilience
- **No job-level requeue on failure** — a failed job is marked `FAILED` once, sent to a
  write-only DLQ nobody consumes. Single biggest remaining resilience gap; needs a decision on
  retry-count semantics and DLQ consumption policy. `MSP_BACKLOG.md` §24.2, §24.4.
- **Model-refusal handling isn't distinct from generic quality-retry** — needs a product decision
  (retry differently? escalate model? fail faster?). `MSP_BACKLOG.md` §24.2.
- **`CircuitBreaker` (exists, works, A2A-bus-only) never extended to litellm/tool-gateway/infra
  failure domains** — design choice on per-domain thresholds, not a blind copy. `MSP_BACKLOG.md` §24.2.
- **Soft-timeout double-publish/finalize race** — mechanism confirmed, not fixed. Needs a decision
  between shielding the finalize phase vs. making enqueue idempotent. `MSP_BACKLOG.md` §27.6, §45.4.

### Async / performance
- **No async Postgres driver anywhere** (`psycopg` sync, not `psycopg.AsyncConnection`) — the
  single biggest structural lever left; DB concurrency is thread-pool-capped everywhere.
  `MSP_BACKLOG.md` §25.4, §25.5.
- **Tool-gateway's async MCP client code (`acall_siem_tool`/`acall_veil_tool`) is fully implemented
  but unused** — `invoke_adapter()` hardcodes the sync variants. `MSP_BACKLOG.md` §25.4.
- **`K8sExecutionBackend`'s poll loop occupies a thread-pool slot for the full job timeout** via
  `time.sleep` instead of an async K8s watch API. `MSP_BACKLOG.md` §25.4.

### Security / hardening
- **`POST /runs/{run_id}/approve-plan` unconditionally returns 501** — dead/never-finished route.
  Wire it up or remove it (product decision). `MSP_BACKLOG.md` §27.6.
- **`bus_signing_key` still a plain env var** — no secrets-manager integration. `MSP_BACKLOG.md` §10.9.
- **No schema/message-type pinning with rug-pull detection** for A2A bus messages or MCP tool
  schemas — confirmed absent, needs design (what counts as "the schema," where hashes live, what
  "alert" means). `MSP_BACKLOG.md` §10.1, §10.2, §44.
- **No separate read-only Postgres role** — one `postgres_user` for all reads and writes everywhere.
  Needs a real `CREATE ROLE`/`GRANT` against the live instance, not just a settings field.
  `MSP_BACKLOG.md` §11.6, §44.
- **Error format is ad-hoc, not RFC 7807** — `web_ui` has a load-bearing dependency on the current
  shape, so this is backend+frontend together. `MSP_BACKLOG.md` §10.11, §41.3.
- **`PersistenceUnavailableError` maps to a generic 500 instead of 503** — mechanically trivial fix,
  but changing a live prod error code is an API-contract call. `MSP_BACKLOG.md` §21.9.
- **ReBAC doesn't scope by persona at the Tool Gateway** — needs an OpenFGA schema migration
  (`workspace_agent` isn't in `datasource#can_query`'s allowed consumer types today).
  `MSP_BACKLOG.md` §11.4.
- **`TOOL_SCOPE_MODE` stuck at `shadow`, can't flip to `enforce`** — two tools
  (`query_siem_readonly`, `dedup_alerts`) are genuinely absent from persona `tools:` lists in
  `agent.yaml`; needs someone with product authority over the catalog to decide the fix, not a
  guess. `MSP_BACKLOG.md` §23.5, §31.
- **`cosign` signing (`job-sign.yml`) is a non-functional stub** — `echo` commands, not real
  `cosign sign`. Needs a keyless-OIDC vs. `COSIGN_PRIVATE_KEY` decision. `MSP_BACKLOG.md` §41.4.
- **`main` has no `required_status_checks` naming `release-gate`** — a PR can merge with every CI
  job red today. Live branch-protection change, needs explicit owner sign-off. `MSP_BACKLOG.md`
  §20.3 (recurring).
- **~15 more `.hex[:12]`/`.hex[:10]` id-generation call sites carry the same PII-redaction-collision
  risk `follow_up_id` had** (fixed) — each needs individual tracing (does the id ever reach
  `redact_pii()`?) before a fix is meaningful; blind sweep would be speculative churn. One candidate
  (`MemoryEntry.id`) already traced and confirmed *not* exposed. `MSP_BACKLOG.md` §48.4, §50.1.

### model-gateway (independent of §1, but §1 needs this too)
- No Dockerfile, no deploy manifest (compose/Helm) — nothing runs it in any real topology yet.
- No NetworkPolicy egress restriction (the actual guarantee that makes gateways non-optional).
- No streaming support (`POST /v1/model/invoke` is request/response only; real usage streams).
- No per-call rate limiting or budget tracking, unlike `tool-gateway`.
- Missing `arch-lint`/`domain-coverage`/`adversarial` CI coverage — no import-linter config, no
  `tests/domain/`, no `tests/adversarial/` yet.
- `MSP_BACKLOG.md` §29.4, §49.

### Product ideas (recorded, not scoped)
- **Agent-session self-looping** — give egregore's own SOC personas a fixed-interval or
  event-gated self-continuation capability, mirroring Claude Code's own `/loop`. Not scoped.
  `MSP_BACKLOG.md` §28.

---

## Working conventions (carried forward from `MSP_BACKLOG.md` §45.5)

- Commits go directly to `feature/microservice-refactoring` — no PRs, no new branches.
- New fail-closed security controls ship via an `off|shadow|enforce` mode setting defaulting to
  `shadow`, never `enforce` by default on a first pass.
- This is a "duplicate everything" codebase (§18) — before calling any fix "done," grep for other
  packages' copies of the same file.
- Targeted `pytest <dir> -q` while iterating; full `scripts/pytest_batches.sh` per package before
  each commit, not after every edit.
- Dispatch real CI (`gh workflow run "Release Gate"`) and check the actual run result before
  calling anything "verified" — a green claim without checking the dispatched run is worth nothing.
