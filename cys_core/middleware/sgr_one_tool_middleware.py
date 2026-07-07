from __future__ import annotations

import inspect
import threading
from collections.abc import Callable
from typing import Any, Awaitable

from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.types import Command

from cys_core.domain.reasoning.sgr_models import REASONING_STEP_TOOL
from cys_core.middleware.sgr_session import SgrSessionState


class SgrOneToolMiddleware(AgentMiddleware):
    """Allow reasoning_step + exactly one action tool per turn."""

    def __init__(self, session: SgrSessionState) -> None:
        super().__init__()
        self._session = session
        self._lock = threading.Lock()

    def _guard_action_tool(self, request: ToolCallRequest) -> ToolMessage | None:
        with self._lock:
            if self._session.action_tools_this_turn >= 1:
                return ToolMessage(
                    content="Only one action tool per turn is allowed after reasoning_step.",
                    tool_call_id=request.tool_call.get("id", ""),
                    status="error",
                )
            self._session.action_tools_this_turn += 1
        return None

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command[Any]],
    ) -> ToolMessage | Command[Any]:
        tool_name = request.tool_call.get("name", "")
        if tool_name == REASONING_STEP_TOOL:
            return handler(request)
        blocked = self._guard_action_tool(request)
        if blocked is not None:
            return blocked
        return handler(request)

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]] | ToolMessage | Command[Any]],
    ) -> ToolMessage | Command[Any]:
        tool_name = request.tool_call.get("name", "")
        if tool_name == REASONING_STEP_TOOL:
            result = handler(request)
            if inspect.isawaitable(result):
                return await result
            return result
        blocked = self._guard_action_tool(request)
        if blocked is not None:
            return blocked
        result = handler(request)
        if inspect.isawaitable(result):
            return await result
        return result
