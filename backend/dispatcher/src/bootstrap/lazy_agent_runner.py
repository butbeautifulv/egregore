from __future__ import annotations

from typing import Any


class LazyInProcessAgentRunner:
    """`AgentRunner`/`PlannerRuntime`-shaped proxy that defers importing
    `cys_core.runtime.agent` (and its langchain/langgraph/litellm dependency)
    until `arun`/`aresume` is actually called.

    Out-of-process execution backends (subprocess/docker/k8s) never call
    these — the actual job execution happens in a child process instead — so
    passing this instead of eagerly resolving `get_runtime()` at composition
    time (`EngagementContainer.get_worker_orchestrator`/`get_meta_planner`)
    keeps those paths from importing the agent runtime's framework
    dependency merely to select an out-of-process execution backend. See
    docs/MICROSERVICES_SPLIT_PLAN.md §1 item 2.

    In backend/dispatcher specifically, `cys_core.runtime.agent` doesn't exist at all
    (moved to backend/agent-runtime) — arun/aresume below are genuinely unreachable here,
    not just deferred; `# ty: ignore[unresolved-import]` reflects that intentionally, not
    a bug to fix.
    """

    async def arun(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        from cys_core.runtime.agent import get_runtime  # ty: ignore[unresolved-import]

        return await get_runtime().arun(*args, **kwargs)

    async def aresume(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        from cys_core.runtime.agent import get_runtime  # ty: ignore[unresolved-import]

        return await get_runtime().aresume(*args, **kwargs)
