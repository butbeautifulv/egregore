from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any, Awaitable

from langchain.agents.middleware.types import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage

from cys_core.llm.tool_call_parsing import tool_calls_from_content
from cys_core.middleware._framework_casts import cast_model_response


def _lift_tool_calls_from_content(message: AIMessage) -> AIMessage:
    if message.tool_calls:
        return message
    if not isinstance(message.content, str) or not message.content.strip():
        return message
    parsed = tool_calls_from_content(message.content)
    if not parsed:
        return message
    return AIMessage(
        content=message.content,
        tool_calls=parsed,
        usage_metadata=message.usage_metadata,
        id=message.id,
        response_metadata=message.response_metadata,
    )


def _process_model_response(response: ModelResponse | AIMessage) -> ModelResponse | AIMessage:
    if isinstance(response, AIMessage):
        return _lift_tool_calls_from_content(response)
    result = getattr(response, "result", None)
    if isinstance(result, list):
        updated: list[Any] = []
        changed = False
        for item in result:
            if isinstance(item, AIMessage):
                lifted = _lift_tool_calls_from_content(item)
                changed = changed or lifted is not item
                updated.append(lifted)
            else:
                updated.append(item)
        if changed:
            return ModelResponse(result=updated, structured_response=getattr(response, "structured_response", None))
    return response


class JsonToolCallMiddleware(AgentMiddleware):
    """Promote JSON tool_calls embedded in assistant content to native tool_calls."""

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse | AIMessage:
        return _process_model_response(handler(request))

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse] | ModelResponse],
    ) -> ModelResponse | AIMessage:
        result = handler(request)
        if inspect.isawaitable(result):
            return _process_model_response(cast_model_response(await result))
        return _process_model_response(cast_model_response(result))
