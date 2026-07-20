# egregore-agent-runtime

The agent-execution runtime (LangChain/LangGraph), extracted from `egregore-worker` as its
own physical package — see `docs/MICROSERVICES_SPLIT_PLAN.md` §1.

**Phase 1 status (2026-07-20):** package split only. This is currently a full copy of
`egregore-worker`'s source tree under a new package identity — same behavior, same tests,
own `pyproject.toml`/`uv.lock`. Nothing calls this package yet; `backend/worker/` still uses
its own physical copy in-process, unchanged. This package exists so the extraction can be
validated (installs, lints, tests green) independently before phases 2-3 wire a real process
boundary and phase 2 strips `backend/worker/` down to a slim `dispatcher` (queue consumption,
budget/trust/policy, `ExecutionBackend` selection only).

Fully self-contained — its own physical copy of domain models, port interfaces, and generic
infra clients (no shared package with any other `backend/` package, see `docs/MSP_BACKLOG.md`
§18).
