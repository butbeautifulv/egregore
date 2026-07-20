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
    docs/MSP_BACKLOG.md §52.2.
    """

    async def arun(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        from cys_core.runtime.agent import get_runtime

        return await get_runtime().arun(*args, **kwargs)

    async def aresume(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        from cys_core.runtime.agent import get_runtime

        return await get_runtime().aresume(*args, **kwargs)
