from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any, Awaitable

from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.types import Command

from cys_core.domain.security.scope import ScopePolicy
from cys_core.middleware._framework_casts import cast_tool_result


class ScopeMiddleware(AgentMiddleware):
    """Least-privilege tool allowlist (cheat sheet §1)."""

    def __init__(
        self,
        allowed_tools: set[str] | list[str],
        blocked_path_patterns: list[str] | None = None,
    ) -> None:
        super().__init__()
        self.policy = ScopePolicy.from_tools(set(allowed_tools), blocked_path_patterns)

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command[Any]],
    ) -> ToolMessage | Command[Any]:
        violation = self._check_scope(request)
        if violation is not None:
            return violation
        return handler(request)

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]] | ToolMessage | Command[Any]],
    ) -> ToolMessage | Command[Any]:
        violation = self._check_scope(request)
        if violation is not None:
            return violation
        result = handler(request)
        if inspect.isawaitable(result):
            return cast_tool_result(await result)
        return cast_tool_result(result)

    def _check_scope(self, request: ToolCallRequest) -> ToolMessage | None:
        tool_name = request.tool_call.get("name", "")
        args = request.tool_call.get("args", {})
        reason = self.policy.check_tool_call(tool_name, args)
        if reason is not None:
            return ToolMessage(
                content=reason,
                tool_call_id=request.tool_call.get("id", ""),
                status="error",
            )
        return None
