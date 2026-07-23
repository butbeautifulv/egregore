# Microservices Split — Active Plan

> Full history, investigations, and reasoning behind every decision below live in
> [`docs/MSP_BACKLOG.md`](MSP_BACKLOG.md). Read [`docs/MSP_START_HERE.md`](MSP_START_HERE.md)
> first if this is a new session. This file is the current to-do list only — strict, to the point,
> no narrative. When an item below is done, move its summary to `MSP_BACKLOG.md` and delete it from
> here.

## Current state (as of 2026-07-22)

Six independent backend packages, no shared package between any of them (deliberate duplication,
`MSP_BACKLOG.md` §18):

| Package | Status |
|---|---|
| `backend/api/` | Deployed (k3s + local), CI-complete |
| `backend/worker/` | **Retired on k3s** (`replicas: 0`); kept for rollback |
| `backend/tool-gateway/` | Deployed, CI-complete |
| `backend/model-gateway/` | Deployed image, wired into `agent-runtime` (selectable, not default) |
| `backend/agent-runtime/` | Deployed as k3s Batch Job executor (`MSP_BACKLOG.md` §68) |
| `backend/dispatcher/` | Deployed on k3s (`EXECUTION_BACKEND=k8s`, `MSP_BACKLOG.md` §68) |

`backend/worker/` monolith is scaled to 0 on offline k3s; dispatcher + agent-runtime Jobs are the
production path. Local dev still supports worker monolith and `dev-dispatcher-split.sh`.

---

## §1 — Remaining work to make the split real

**Goal**: `dispatcher` and `agent-runtime` run as genuinely separate, connected services, and the
agent core behind `agent-runtime` can be swapped for a different implementation without touching
`dispatcher` — "switch core to any agent on the market, inside a safe system."

1. **Deploy bootstrap for `docker`/`k8s` `ExecutionBackend` modes.** `subprocess`/same-host mode is
   proven (`MSP_BACKLOG.md` §56). **`k8s` mode deployed on offline P30** (`MSP_BACKLOG.md` §68):
   dispatcher Deployment + agent-runtime Batch Jobs + Helm/RBAC/Kaniko split images. `docker` backend
   still needs dispatcher container `docker` CLI + `/var/run/docker.sock` — deliberately deferred.
   `MSP_BACKLOG.md` §52.4, §52.5.
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
- **§8.4's "core hardcodes SOC domain" cross-cutting refactor is DONE, all 6 points closed**
  (`§62` point 3, `§63` point 4, `§64` point 5, `§70` point 2, `§71` point 1, `§72` point 6 —
  full history in `MSP_BACKLOG.md` §8/§24.1/§62/§63/§64/§70/§71/§72). Point 6's acceptance test
  (a toy non-SOC pack proving `cys_core/domain` needs zero changes) is genuinely met:
  `gaia-benchmark`'s `gaia_solver` persona turned out to already be domain-clean (zero
  SIEM/Veil/Nessus/compliance tools, generic `output_schema`) — verified end to end with a
  standalone script: `load_profile_pack_for("gaia-benchmark")` + a fresh `ToolRegistry` under
  `PROFILE_PACK_ID=gaia-benchmark` carry zero SOC tools, `schema_registry.get("SocFinding")`
  correctly raises `KeyError`. Finding this exposed one more real gap in `§63`'s own scope: 13
  SOC-specific tools (`query_siem_readonly`, `parse_sast_report`, compliance/timeline tools, etc.)
  were defined inline in `cys_core/registry/tools.py` and baked unconditionally into every pack's
  `ToolRegistry` — `§63` only gated the three *external* builder calls
  (`build_veil_tools`/`build_siem_tools`/`build_nessus_tools`), never these. Fixed in `§72`: a new
  `"cybersec-core"` tool domain, gated the same `PROFILE_PACK_ID` way, added to
  `CYBERSEC_SOC_PRODUCT.tool_domains` so the real pack's behavior is unchanged.
  **Known, explicitly-deferred residuals** (not silently swept under "done"):
  `result_validator.py`'s `"ConsultantFinding"`-literal special-casing (`§70.4`); `tool_risk`
  (`ACTION_RISK_MAPPING`) has a similar "leaks into every profile" shape but gating it alone would
  be cosmetic without also changing `classify_tool_risk_pure`'s own fallback (`§62.5`);
  `CYBERSEC_SOC_PRODUCT.personas`' 2-vs-17-persona data-completeness gap still blocks
  `cybersec-soc` itself from using the pack-filtered catalog path (`§64.1`/`§64.4`); no
  catalog-driven validation wired for `EventType`/`WorkerAgentName` beyond `str` (none existed to
  piggyback on, `§71`).
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
