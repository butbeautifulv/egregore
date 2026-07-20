# Microservices Split — Active Plan

> Full history, investigations, and reasoning behind every decision below live in
> [`docs/MSP_BACKLOG.md`](MSP_BACKLOG.md) (§0–§55). This file is the current to-do list only —
> straight to the point, no narrative. When an item below is done, move its summary to
> `MSP_BACKLOG.md` and delete it from here.

## Current state (as of 2026-07-20)

Six independent backend packages, no shared package between any of them (each carries its own
physical copy of `cys_core.domain`/`bootstrap`/generic infra — deliberate duplication, `MSP_BACKLOG.md` §18):

| Package | Job | Status |
|---|---|---|
| `backend/api/` | FastAPI ingress/CRUD, event routing, HITL resume over HTTP | Deployed, CI-complete |
| `backend/worker/` | Original monolith (agent runtime + queue consumption + control-plane daemons) | **Deployed, unchanged** — not yet retired |
| `backend/tool-gateway/` | PEP for sandboxed agent tool calls (async stdlib server) | Deployed, CI-complete |
| `backend/model-gateway/` | LLM-call chokepoint (input sanitize, prompt-digest check, output-leakage guard) | Deployed image (Dockerfile+CI), wired into `agent-runtime` (selectable, not default) |
| `backend/agent-runtime/` | Swappable agent-execution runtime (LangGraph today) — full copy of `worker` | Package exists, CI-green, **process boundary proven live (local sandbox), not deployed** |
| `backend/dispatcher/` | Queue + budget/policy + `ExecutionBackend` dispatch, no agent-execution engine | Package exists, CI-green, **process boundary proven live (local sandbox), not deployed** |

`backend/worker/` is not deleted or renamed — stays deployed until `dispatcher`+`agent-runtime` are
proven out end-to-end and a deliberate cutover retires it. See `MSP_BACKLOG.md` §52 for exactly how
the split (§52.1), the `AgentRunner` registry (§52.3), the deploy bootstrap (§52.5), and the
tool-gateway async fix (§52.6) were built and verified, §53 for the same async fix synced to
`worker`/`agent-runtime`, and §54 for the `model-gateway` wiring (including two real CI failures
caught and fixed properly, not papered over).

---

## §1 — Remaining work to make the split real

**Goal**: `dispatcher` and `agent-runtime` run as genuinely separate, connected services, and the
agent core behind `agent-runtime` can be swapped for a different implementation without touching
`dispatcher` — "switch core to any agent on the market, inside a safe system."

1. **Deploy bootstrap for `docker`/`k8s` `ExecutionBackend` modes.** `subprocess`/same-host mode is
   proven (see below) via `scripts/dev-dispatcher-split.sh`. `docker`/`k8s` modes (needed for a real
   multi-container/multi-host deploy) still have no `docker-compose.dev.yml` entry or Helm/K8s
   manifest — `docker` backend needs the dispatcher container to hold the `docker` CLI and a
   bind-mounted host `/var/run/docker.sock` (privilege-escalation-shaped, needs its own review).
   Deliberately deferred — not yet decided. `MSP_BACKLOG.md` §52.4, §52.5.
2. **HITL pause/resume redesign for the cross-process case.** Today's mechanism
   (`langgraph.interrupt()` + checkpointer) is in-process-shaped and won't survive `agent-runtime`
   being a separate process. Design exists (refuse-then-retry with an `approval_id` token, reusing
   `ResumeHitlJob`'s anti-tampering pattern) but is **not implemented** — do this before relying on
   the split in production with HITL-gated personas. Neither `AgentRunner` implementation
   (`langgraph` or `react`) supports resume across process boundaries yet. `MSP_BACKLOG.md` §35.
3. **Sandbox isolation beyond K8s/Docker** (gVisor `runtimeClassName`, Kata Containers) — documented
   only, zero code. Only after item 1 (deploy bootstrap) is stable. `MSP_BACKLOG.md` §22.5.

Process boundary is **proven**, `subprocess`/same-host only: `dispatcher` and `agent-runtime` have
run live as two connected processes, a real `WorkerJob` flowed end-to-end through
`SubprocessExecutionBackend` into a real DeepSeek LLM call with tools bound, and the result
round-tripped back cleanly. Two real bugs were found and fixed along the way — litellm's own stdout
banners were corrupting the parent's JSON parse, and `agent-runtime`'s trimmed dependencies were
missing `fastapi` (a hard requirement of litellm's tool-calling path, not of agent-runtime itself),
which had silently broken every tool-using persona call. `MSP_BACKLOG.md` §56.

A second `AgentRunner` implementation is **registered**: `"react"`/`MinimalReactAgentRunner`
(`cys_core/runtime/react_agent.py`) — a hand-written call-model → maybe-call-tool → repeat loop,
zero LangGraph/middleware dependency, per the user's explicit "minimal" choice. Live-tested the same
way as the process-boundary proof: a real DeepSeek tool call (`list_incidents`) executed and fed
back correctly. Does not support HITL resume (see item 2) — a tool call matching a persona's
`hitl_tools` is refused outright rather than silently allowed. `MSP_BACKLOG.md` §56.6.

---

## §2 — Everything else, by theme (independent of §1)

### Core architecture / domain
- **Core still hardcodes SOC domain in 6 places** (`EventType`/`WorkerAgentName` closed `Literal`s,
  11 concrete `Finding` subclasses, `ESCALATION_ONLY_PATHS`/`READ_ONLY_TOOLS`, unconditional
  `ToolRegistry` SIEM/Veil/Nessus registration, `DEFAULT_PROFILE_ID`). Large cross-cutting refactor,
  target model already written. `MSP_BACKLOG.md` §8, §24.1.
- **Semantic/long-term agent memory tier doesn't exist** — `memory_type` schema has `lesson`/
  `preference` slots, nothing ever writes them. `MSP_BACKLOG.md` §9.

### Job resilience
- **No job-level requeue on failure** — a failed job is marked `FAILED` once, sent to a write-only
  DLQ nobody consumes. Needs a decision on retry-count semantics and DLQ consumption policy.
  `MSP_BACKLOG.md` §24.2, §24.4.
- **Model-refusal handling isn't distinct from generic quality-retry** — needs a product decision.
  `MSP_BACKLOG.md` §24.2.
- **`CircuitBreaker` never extended beyond the A2A bus** to litellm/tool-gateway/infra failure
  domains. `MSP_BACKLOG.md` §24.2.
- **Soft-timeout double-publish/finalize race** — confirmed, not fixed. `MSP_BACKLOG.md` §27.6, §45.4.

### Async / performance
- **No async Postgres driver anywhere** (`psycopg` sync) — the single biggest structural lever left;
  DB concurrency is thread-pool-capped everywhere. `MSP_BACKLOG.md` §25.4, §25.5.

### Security / hardening
- **`POST /runs/{run_id}/approve-plan`** unconditionally returns 501 — wire it up or remove it.
  `MSP_BACKLOG.md` §27.6.
- **`bus_signing_key` still a plain env var** — no secrets-manager integration. `MSP_BACKLOG.md` §10.9.
- **No schema/message-type pinning with rug-pull detection** for A2A bus messages or MCP tool
  schemas. `MSP_BACKLOG.md` §10.1, §10.2, §44.
- **No separate read-only Postgres role** — needs a real `CREATE ROLE`/`GRANT` against the live
  instance. `MSP_BACKLOG.md` §11.6, §44.
- **Error format is ad-hoc, not RFC 7807** — `web_ui` has a load-bearing dependency on the current
  shape. `MSP_BACKLOG.md` §10.11, §41.3.
- **`PersistenceUnavailableError` maps to 500 instead of 503** — changing a live prod error code is
  an API-contract call. `MSP_BACKLOG.md` §21.9.
- **ReBAC doesn't scope by persona at the Tool Gateway** — needs an OpenFGA schema migration.
  `MSP_BACKLOG.md` §11.4.
- **`TOOL_SCOPE_MODE` stuck at `shadow`** — two tools missing from persona `agent.yaml` allowlists;
  needs product authority over the catalog. `MSP_BACKLOG.md` §23.5, §31.
- **`cosign` signing (`job-sign.yml`) is a non-functional stub** — needs a keyless-OIDC vs.
  `COSIGN_PRIVATE_KEY` decision. `MSP_BACKLOG.md` §41.4.
- **`main` has no `required_status_checks` naming `release-gate`** — a PR can merge with every CI
  job red today. Needs explicit owner sign-off. `MSP_BACKLOG.md` §20.3.
- **~15 more `.hex[:12]`/`.hex[:10]` id-generation sites** carry the same PII-redaction-collision
  risk `follow_up_id` had — each needs individual tracing before a fix is meaningful.
  `MSP_BACKLOG.md` §48.4, §50.1.

### model-gateway
- No deploy manifest (compose/Helm) — Dockerfile exists now (§54), no compose/Helm entry yet, same
  gap as agent-runtime/dispatcher (§1 item 2).
- No NetworkPolicy egress restriction.
- No streaming support (`POST /v1/model/invoke` is request/response only) — `agent-runtime`'s
  `ModelGatewayChatModel._astream` works around this with a single-chunk fallback (§54), not a fix.
- No per-call rate limiting or budget tracking, unlike `tool-gateway`.
- `arch-lint` CI coverage added (`import-linter` + `scripts/verify_import_boundaries.py` +
  `tests/architecture/`, scoped to this package's actual 4-layer structure — no
  infrastructure/registry/runtime/middleware layers here to check). `domain-coverage`
  (`--cov-fail-under=100` on `tests/domain/`) and `adversarial` still missing — `domain-coverage`
  needs a `tests/domain/` suite written from scratch first (none exists), a separate, larger effort
  than the arch-lint port. `MSP_BACKLOG.md` §57.
- `MSP_BACKLOG.md` §29.4, §49, §54.

### Product ideas (recorded, not scoped)
- **Agent-session self-looping** — event-gated self-continuation for egregore's own SOC personas,
  mirroring Claude Code's `/loop`. `MSP_BACKLOG.md` §28.

---

## Working conventions

- Commits go directly to `feature/microservice-refactoring` — no PRs, no new branches.
- New fail-closed security controls ship via an `off|shadow|enforce` mode setting defaulting to
  `shadow`, never `enforce` by default on a first pass.
- This is a "duplicate everything" codebase (§18) — before calling any fix "done," grep for other
  packages' copies of the same file.
- Never run test suites locally — dispatch CI (`gh workflow run "Release Gate"`) in the background
  and keep working on the next item; don't block the session waiting on a run. Only the *claim* of
  "verified"/"done" requires checking the actual run result first — dispatching doesn't.
  `ruff`/`ty check`/`lint-imports`/`docker build`/`hadolint`/`uv lock --check` are fine locally
  (static checks, not test suites).
