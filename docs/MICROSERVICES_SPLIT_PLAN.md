# Microservices Split — Active Plan

> Full history, investigations, and reasoning behind every decision below live in
> [`docs/MSP_BACKLOG.md`](MSP_BACKLOG.md). Read [`docs/MSP_START_HERE.md`](MSP_START_HERE.md)
> first if this is a new session. This file is the current to-do list only — strict, to the point,
> no narrative. When an item below is done, move its summary to `MSP_BACKLOG.md` and delete it from
> here.

## Current state (as of 2026-07-20)

Six independent backend packages, no shared package between any of them (deliberate duplication,
`MSP_BACKLOG.md` §18):

| Package | Status |
|---|---|
| `backend/api/` | Deployed, CI-complete |
| `backend/worker/` | **Deployed, unchanged** — original monolith, not yet retired |
| `backend/tool-gateway/` | Deployed, CI-complete |
| `backend/model-gateway/` | Deployed image, wired into `agent-runtime` (selectable, not default) |
| `backend/agent-runtime/` | CI-green, process boundary proven live (local sandbox), not deployed |
| `backend/dispatcher/` | CI-green, process boundary proven live (local sandbox), not deployed |

`backend/worker/` stays deployed until `dispatcher`+`agent-runtime` are proven out end-to-end and a
deliberate cutover retires it.

---

## §1 — Remaining work to make the split real

**Goal**: `dispatcher` and `agent-runtime` run as genuinely separate, connected services, and the
agent core behind `agent-runtime` can be swapped for a different implementation without touching
`dispatcher` — "switch core to any agent on the market, inside a safe system."

1. **Deploy bootstrap for `docker`/`k8s` `ExecutionBackend` modes.** `subprocess`/same-host mode is
   proven (`MSP_BACKLOG.md` §56). `docker`/`k8s` modes still have no `docker-compose.dev.yml` entry
   or Helm/K8s manifest — `docker` backend needs the dispatcher container to hold the `docker` CLI
   and a bind-mounted host `/var/run/docker.sock` (privilege-escalation-shaped, needs its own
   review). Deliberately deferred — not yet decided. `MSP_BACKLOG.md` §52.4, §52.5.
2. **HITL pause/resume redesign for the cross-process case.** Design (`§35`, refuse-then-retry
   with an approval token) is built both sides for the LangGraph path and **proven live end to end**
   (`§61`): `tool-gateway` classifies risk and mints/verifies approval tokens (`§58`);
   `worker`/`agent-runtime`'s `SecurityMiddleware` notices a gateway `hitl_required` refusal after
   `handler(request)` returns, pauses with `interrupt()` there, persists the pause to Postgres, and
   retries with the token on approval (`§59`) — a real DeepSeek-driven run against a real live
   tool-gateway server genuinely paused, persisted, resumed, and completed with real tool execution
   (`§61`), which also found and fixed a real bug (`§61.2`: the HTTP wire DTOs were silently
   dropping the new fields). `TOOL_HITL_MODE` still defaults to `shadow` — changes nothing live yet.
   **What the live proof didn't cover** (`§61.4`): the reject path live, both `SecurityMiddleware`
   checks running together (real default; the proof isolated the new one), more than one
   tool/persona, concurrent runs. Flipping `TOOL_HITL_MODE`'s default is a product decision, not
   just a technical one, and hasn't been made. Separately, `MinimalReactAgentRunner`'s tools don't
   route through tool-gateway's `InvokeTool` at all (they call `siem_mcp`/`veil`/`nessus` adapters
   directly) — a real, older, already-documented gap (`§58.1`'s "4 `InvokeTool` copies" finding),
   not closed by `§59`/`§61` and not in scope for the approval-token retry work. `MSP_BACKLOG.md`
   §35, §58, §59, §61.
3. **Sandbox isolation beyond K8s/Docker** (gVisor `runtimeClassName`, Kata Containers) — documented
   only, zero code. Only after item 1 is stable. `MSP_BACKLOG.md` §22.5.

---

## §2 — Everything else, by theme (independent of §1)

### Core architecture / domain
- **Core still hardcodes SOC domain, 4 of 6 points remaining** (`EventType`/`WorkerAgentName`
  closed `Literal`s, 11 concrete `Finding` subclasses, `product_packs.py` never wired up as the
  real runtime pack loader, no toy non-SOC-pack acceptance test proving `cys_core/domain` needs
  zero changes). Two points done: (`§62`) `ESCALATION_ONLY_PATHS`/`READ_ONLY_TOOLS`/
  `PLAN_BLOCKED_TOOLS`/`MUTATING_TOOLS` no longer leak from `cybersec-soc` into every other profile
  pack unconditionally; (`§63`) `ToolRegistry`'s SIEM/Veil/Nessus tool construction/registration is
  now conditional on the active profile pack (`PROFILE_PACK_ID` env var → `ProductProfilePack.
  tool_domains`) instead of an unconditional module-import side effect. `tool_risk`
  (`ACTION_RISK_MAPPING`) has a similar "leaks into every profile" shape but gating it alone would
  be cosmetic without also changing `classify_tool_risk_pure`'s own fallback — a separate, riskier
  pass, not picked up here (see `§62.5`). Large cross-cutting refactor overall, target model
  already written. `MSP_BACKLOG.md` §8, §24.1, §62, §63.
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
- No deploy manifest (compose/Helm) — same gap as agent-runtime/dispatcher (§1 item 1).
- No NetworkPolicy egress restriction.
- No streaming support (`POST /v1/model/invoke` is request/response only) — `agent-runtime`'s
  `ModelGatewayChatModel._astream` works around this with a single-chunk fallback, not a fix.
- No per-call rate limiting or budget tracking, unlike `tool-gateway`.
- `domain-coverage` (`--cov-fail-under=100` on `tests/domain/`) and `adversarial` CI jobs still
  missing — `domain-coverage` needs a `tests/domain/` suite written from scratch first (none
  exists; `arch-lint` coverage already landed, §57). `MSP_BACKLOG.md` §57.
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
  `ruff`/`ty check`/`lint-imports`/`docker build`/`hadolint`/`uv lock --check`/
  `pytest --collect-only` are fine locally (static/import-resolution checks, not test-body
  execution — see `MSP_START_HERE.md` §5 for why `--collect-only` earned its place here).
