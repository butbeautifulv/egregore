from __future__ import annotations

from typing import Any, cast

from langchain.agents.middleware.types import ModelResponse
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.types import Command


def cast_model_response(result: object) -> ModelResponse | AIMessage:
    return cast(ModelResponse | AIMessage, result)


def cast_tool_result(result: object) -> ToolMessage | Command[Any]:
    return cast(ToolMessage | Command[Any], result)
