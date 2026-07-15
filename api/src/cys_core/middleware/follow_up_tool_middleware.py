from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Awaitable

import structlog
from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.types import Command

from cys_core.application.tools.providers.siem import SIEM_TOOL_NAMES
from cys_core.infrastructure.tools.adapters.veil_mcp import is_veil_tool
from cys_core.middleware._framework_casts import cast_tool_result

logger = structlog.get_logger(__name__)

_BLOCKED_PREFIXES = frozenset({"follow_up_qa", "follow_up_orchestrate"})
_ALLOWED_ORCHESTRATE_TOOLS = frozenset(
    {
        "spawn_worker",
        "delegate_research",
        "reasoning_step",
        "reasoning_check",
        "load_skill",
        "search_personas",
        "search_tools",
        "ask_user",
    }
)


class FollowUpToolMiddleware(AgentMiddleware):
    """Block SIEM/Veil for follow-up orchestrator jobs; allow spawn_worker."""

    def _work_kind(self) -> str:
        value = structlog.contextvars.get_contextvars().get("work_kind")
        return value if isinstance(value, str) else ""

    def _blocked(self, request: ToolCallRequest, message: str) -> ToolMessage:
        return ToolMessage(
            content=message,
            tool_call_id=request.tool_call.get("id", ""),
            status="error",
        )

    def _check(self, request: ToolCallRequest) -> ToolMessage | None:
        work_kind = self._work_kind()
        if work_kind not in _BLOCKED_PREFIXES:
            return None
        tool_name = str(request.tool_call.get("name", ""))
        if not tool_name:
            return None
        if work_kind == "follow_up_orchestrate" and tool_name in _ALLOWED_ORCHESTRATE_TOOLS:
            return None
        if tool_name in SIEM_TOOL_NAMES or is_veil_tool(tool_name):
            return self._blocked(request, "Follow-up orchestrator cannot call SIEM/Veil tools directly.")
        if work_kind == "follow_up_qa" and tool_name not in _ALLOWED_ORCHESTRATE_TOOLS:
            siem_prefixes = ("investigate_", "get_", "search_events")
            if any(tool_name.startswith(prefix) for prefix in siem_prefixes):
                return self._blocked(request, "Follow-up Q&A is read-only; cite existing evidence only.")
        return None

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command],
    ) -> ToolMessage | Command:
        blocked = self._check(request)
        if blocked is not None:
            return blocked
        return handler(request)

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command] | ToolMessage | Command],
    ) -> ToolMessage | Command:
        blocked = self._check(request)
        if blocked is not None:
            return blocked
        result = handler(request)
        if inspect.isawaitable(result):
            return cast_tool_result(await result)
        return cast_tool_result(result)
