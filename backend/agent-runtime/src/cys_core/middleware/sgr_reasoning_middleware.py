from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any, Awaitable

from langchain.agents.middleware.types import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.types import Command

from cys_core.application.reasoning.sgr_policy import ResolvedSgrPolicy
from cys_core.domain.reasoning.sgr_models import REASONING_STEP_TOOL, SchemaGuidedReasoningStep
from cys_core.middleware._framework_casts import cast_model_response, cast_tool_result
from cys_core.middleware.sgr_session import SgrSessionState

_REASONING_REMINDER = (
    "Before any action tool, you MUST call reasoning_step with structured fields: "
    "reasoning_steps, current_situation, plan_status, remaining_steps, enough_data, task_completed."
)


class SchemaGuidedReasoningMiddleware(AgentMiddleware):
    """Enforce SGR reasoning_step before action tools."""

    def __init__(self, *, policy: ResolvedSgrPolicy, session: SgrSessionState | None = None) -> None:
        super().__init__()
        self._policy = policy
        self._session = session or SgrSessionState()

    @property
    def session(self) -> SgrSessionState:
        return self._session

    def _prepend_reasoning_reminder(self, request: ModelRequest) -> ModelRequest:
        from langchain_core.messages import SystemMessage

        if request.system_message is not None:
            content = str(request.system_message.content or "")
            return request.override(
                system_message=SystemMessage(content=f"{_REASONING_REMINDER}\n\n{content}"),
            )
        messages = list(request.messages)
        messages.insert(0, SystemMessage(content=_REASONING_REMINDER))
        return request.override(messages=messages)

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse | AIMessage:
        self._session.reset_turn()
        if self._policy.enabled and self._policy.require_before_action:
            request = self._prepend_reasoning_reminder(request)
        return handler(request)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse] | ModelResponse],
    ) -> ModelResponse | AIMessage:
        self._session.reset_turn()
        if self._policy.enabled and self._policy.require_before_action:
            request = self._prepend_reasoning_reminder(request)
        result = handler(request)
        if inspect.isawaitable(result):
            return cast_model_response(await result)
        return cast_model_response(result)

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command[Any]],
    ) -> ToolMessage | Command[Any]:
        tool_name = request.tool_call.get("name", "")
        if not self._policy.enabled:
            return handler(request)
        if self._session.is_reasoning_tool(tool_name):
            result = handler(request)
            record_reasoning_from_tool_args(self._session, request.tool_call.get("args", {}))
            return result
        if self._policy.require_before_action and not self._session.reasoning_done:
            return ToolMessage(
                content=f"Call {REASONING_STEP_TOOL} before using {tool_name}.",
                tool_call_id=request.tool_call.get("id", ""),
                status="error",
            )
        return handler(request)

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]] | ToolMessage | Command[Any]],
    ) -> ToolMessage | Command[Any]:
        tool_name = request.tool_call.get("name", "")
        if not self._policy.enabled:
            result = handler(request)
            if inspect.isawaitable(result):
                return cast_tool_result(await result)
            return cast_tool_result(result)
        if self._session.is_reasoning_tool(tool_name):
            result = handler(request)
            if inspect.isawaitable(result):
                result = await result
            record_reasoning_from_tool_args(self._session, request.tool_call.get("args", {}))
            return cast_tool_result(result)
        if self._policy.require_before_action and not self._session.reasoning_done:
            return ToolMessage(
                content=f"Call {REASONING_STEP_TOOL} before using {tool_name}.",
                tool_call_id=request.tool_call.get("id", ""),
                status="error",
            )
        result = handler(request)
        if inspect.isawaitable(result):
            return cast_tool_result(await result)
        return cast_tool_result(result)


def record_reasoning_from_tool_args(session: SgrSessionState, args: dict[str, Any]) -> None:
    try:
        step = SchemaGuidedReasoningStep.model_validate(args)
    except Exception:
        return
    session.mark_reasoning(step)
    try:
        from cys_core.observability.metrics import metrics

        metrics.sgr_reasoning_steps_total.inc()
    except Exception:
        pass
