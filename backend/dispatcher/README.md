# egregore-dispatcher

Consumes `WorkerJob` messages from the queue, resolves budget/trust/policy, and dispatches
agent execution to a sandboxed `ExecutionBackend` (subprocess/K8s/Docker) — extracted from
`egregore-worker` as its own physical package (`docs/MICROSERVICES_SPLIT_PLAN.md` §1).

**Does not contain the agent execution engine.** `cys_core/runtime` (the LangGraph agent loop)
and `cys_core/middleware` (its LangChain middleware stack) live in `backend/agent-runtime/` now
— this package has neither, and doesn't depend on `langchain`/`deepagents`. `EXECUTION_BACKEND`
defaults to `subprocess` here (not `in_process`, which is structurally unsupported — see
`bootstrap/containers/engagement_container.py::get_worker_orchestrator()`). Set
`AGENT_RUNTIME_PYTHON_EXECUTABLE` to `backend/agent-runtime`'s own venv python so
`SubprocessExecutionBackend` spawns jobs there instead of trying to run them in dispatcher's own
(agent-runtime-dependency-free) interpreter.

Still keeps `langchain-core`/`langgraph`/`litellm` as real dependencies: `cys_core/llm`'s
message/tool vocabulary and `cys_core/persistence.py`'s LangGraph checkpoint types are used by
tool-registry/job-routing code that isn't itself the agent loop (traced in full in
`docs/MSP_BACKLOG.md` §52.1) — not yet decoupled from those lower-level types.

Fully self-contained — its own physical copy of domain models, port interfaces, and generic
infra clients (no shared package with any other `backend/` package, see `docs/MSP_BACKLOG.md`
§18).
