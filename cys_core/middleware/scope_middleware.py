from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any, Awaitable

from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.types import Command

from cys_core.security.guardrails import SecurityViolation


class ScopeMiddleware(AgentMiddleware):
    """Least-privilege tool allowlist (cheat sheet §1)."""

    def __init__(
        self,
        allowed_tools: set[str],
        blocked_path_patterns: list[str] | None = None,
    ) -> None:
        super().__init__()
        self.allowed_tools = allowed_tools
        self.blocked_path_patterns = blocked_path_patterns or [
            "*.env",
            "*.key",
            "*.pem",
            "*secret*",
        ]

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
            return await result
        return result

    def _check_scope(self, request: ToolCallRequest) -> ToolMessage | None:
        tool_name = request.tool_call.get("name", "")
        if tool_name not in self.allowed_tools:
            return ToolMessage(
                content=f"Access denied: tool '{tool_name}' is not allowed for this agent.",
                tool_call_id=request.tool_call.get("id", ""),
                status="error",
            )
        args = request.tool_call.get("args", {})
        for key, value in args.items():
            if "path" in key.lower() and isinstance(value, str):
                lower = value.lower()
                for pattern in self.blocked_path_patterns:
                    clean = pattern.replace("*", "")
                    if clean and clean in lower:
                        return ToolMessage(
                            content=f"Access denied: path '{value}' matches blocked pattern.",
                            tool_call_id=request.tool_call.get("id", ""),
                            status="error",
                        )
        return None
