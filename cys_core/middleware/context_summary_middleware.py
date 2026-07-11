from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Awaitable

from langchain.agents.middleware.types import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, AnyMessage

from cys_core.application.ports.context_summarizer import ContextSummarizerPort
from cys_core.middleware._framework_casts import cast_model_response
from cys_core.application.runs.message_trim import heal_orphaned_tool_messages
from cys_core.application.runs.message_trim import trim_tool_results
from cys_core.application.runtime_config import get_context_summary_max_messages, get_keep_tool_results


class ContextSummaryMiddleware(AgentMiddleware):
    """Trim overflowing message history using ContextSummarizerPort."""

    def __init__(
        self,
        summarizer: ContextSummarizerPort,
        *,
        goal: str = "",
        max_messages: int | None = None,
        keep_tool_results: int | None = None,
    ) -> None:
        super().__init__()
        self.summarizer = summarizer
        self.goal = goal
        self.max_messages = max_messages or get_context_summary_max_messages()
        self.keep_tool_results = keep_tool_results if keep_tool_results is not None else get_keep_tool_results()
        self.last_summary = ""

    def _trim_messages(self, messages: list[AnyMessage]) -> list[AnyMessage]:
        trimmed_tools = trim_tool_results(list(messages), keep=self.keep_tool_results)
        if len(trimmed_tools) <= self.max_messages:
            return heal_orphaned_tool_messages(trimmed_tools)
        system = [m for m in trimmed_tools if getattr(m, "type", "") == "system" or getattr(m, "role", "") == "system"]
        other = [m for m in trimmed_tools if m not in system]
        max_other = max(1, self.max_messages - len(system))
        trimmed = heal_orphaned_tool_messages(other[-max_other:])
        return [*system, *trimmed]

    def _maybe_summarize(self, messages: list[AnyMessage]) -> list[AnyMessage]:
        trimmed = self._trim_messages(messages)
        if len(trimmed) <= self.max_messages:
            return trimmed
        text_parts: list[str] = []
        for msg in trimmed:
            text_parts.append(str(getattr(msg, "content", "")))
        combined = "\n".join(text_parts)
        self.last_summary = self.summarizer.summarize(
            goal=self.goal,
            messages_text=combined,
            prior_summary=self.last_summary,
        )
        summary_message = AIMessage(content=f"[Context summary]\n{self.last_summary}")
        head = trimmed[0] if trimmed else summary_message
        tail = trimmed[-1] if len(trimmed) > 1 else summary_message
        return heal_orphaned_tool_messages([head, summary_message, tail])

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse | AIMessage:
        updated = request.override(messages=self._maybe_summarize(list(request.messages)))
        return handler(updated)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse] | ModelResponse],
    ) -> ModelResponse | AIMessage:
        updated = request.override(messages=self._maybe_summarize(list(request.messages)))
        result = handler(updated)
        if inspect.isawaitable(result):
            return cast_model_response(await result)
        return cast_model_response(result)
