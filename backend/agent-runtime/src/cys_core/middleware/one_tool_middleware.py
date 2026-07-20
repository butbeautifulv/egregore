from __future__ import annotations

import inspect
import threading
from collections.abc import Callable
from typing import Any, Awaitable

import structlog
from langchain.agents.middleware.types import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.types import Command

from cys_core.application.workers.tool_execution_tracker import siem_investigate_done
from cys_core.middleware._framework_casts import cast_model_response, cast_tool_result


class OneToolPerTurnMiddleware(AgentMiddleware):
    """Limit agent to a single tool invocation per model turn (DeepAgent-style discipline)."""

    def __init__(self, *, persona: str = "") -> None:
        super().__init__()
        self.persona = persona
        self._tool_calls_this_turn = 0
        self._lock = threading.Lock()

    def _max_tools_per_turn(self) -> int:
        if self.persona != "soc":
            return 1
        job_id = structlog.contextvars.get_contextvars().get("job_id")
        investigation_id = structlog.contextvars.get_contextvars().get("correlation_id")
        if not isinstance(job_id, str):
            job_id = ""
        if not isinstance(investigation_id, str):
            investigation_id = ""
        if siem_investigate_done(job_id, investigation_id, persona="soc"):
            return 1
        return 2

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse | AIMessage:
        self._tool_calls_this_turn = 0
        return handler(request)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse] | ModelResponse],
    ) -> ModelResponse | AIMessage:
        self._tool_calls_this_turn = 0
        result = handler(request)
        if inspect.isawaitable(result):
            return cast_model_response(await result)
        return cast_model_response(result)

    def _guard_tool_call(self, request: ToolCallRequest) -> ToolMessage | None:
        with self._lock:
            self._tool_calls_this_turn += 1
            if self._tool_calls_this_turn > self._max_tools_per_turn():
                return ToolMessage(
                    content="Only one tool call per turn is allowed. Complete this step before invoking another tool.",
                    tool_call_id=request.tool_call.get("id", ""),
                    status="error",
                )
        return None

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command[Any]],
    ) -> ToolMessage | Command[Any]:
        blocked = self._guard_tool_call(request)
        if blocked is not None:
            return blocked
        return handler(request)

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]] | ToolMessage | Command[Any]],
    ) -> ToolMessage | Command[Any]:
        blocked = self._guard_tool_call(request)
        if blocked is not None:
            return blocked
        result = handler(request)
        if inspect.isawaitable(result):
            return cast_tool_result(await result)
        return cast_tool_result(result)
