from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable, Sequence
from typing import Any, cast

import litellm
from langchain_core.language_models import LanguageModelInput
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import Field

from cys_core.llm.tool_call_parsing import (
    litellm_tool_calls_to_langchain,
    tool_calls_from_content,
)


def normalize_messages_for_litellm(messages: list[BaseMessage]) -> list[BaseMessage]:
    """Merge all SystemMessage entries into a single system message at the start."""
    system_parts: list[str] = []
    rest: list[BaseMessage] = []
    for message in messages:
        if isinstance(message, SystemMessage):
            content = message.content
            if isinstance(content, str) and content.strip():
                system_parts.append(content)
            elif content:
                system_parts.append(str(content))
        else:
            rest.append(message)
    if not system_parts:
        return rest
    return [SystemMessage(content="\n\n".join(system_parts)), *rest]


def _normalize_tool_choice(value: str | dict[str, Any] | None) -> str | dict[str, Any] | None:
    """vLLM rejects OpenAI-style tool_choice=any; map to auto."""
    if value is None:
        return None
    if isinstance(value, str) and value.lower() in {"any", "required"}:
        return "auto"
    return value


def tools_to_openai_schema(
    tools: Sequence[dict[str, Any] | type | Callable[..., Any] | BaseTool],
) -> list[dict[str, Any]]:
    schemas: list[dict[str, Any]] = []
    for tool in tools:
        if isinstance(tool, dict):
            schemas.append(cast(dict[str, Any], tool))
        else:
            schemas.append(convert_to_openai_tool(cast(Any, tool)))
    return schemas


def _serialize_tool_arguments(args: Any) -> str:
    if isinstance(args, str):
        return args
    return json.dumps(args if isinstance(args, dict) else {})


def _to_litellm_message(message: BaseMessage) -> dict[str, Any]:
    if isinstance(message, SystemMessage):
        return {"role": "system", "content": message.content}
    if isinstance(message, HumanMessage):
        return {"role": "user", "content": message.content}
    if isinstance(message, AIMessage):
        payload: dict[str, Any] = {"role": "assistant", "content": message.content or ""}
        if message.tool_calls:
            payload["tool_calls"] = [
                {
                    "id": tc.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": _serialize_tool_arguments(tc.get("args", {})),
                    },
                }
                for tc in message.tool_calls
            ]
        return payload
    if isinstance(message, ToolMessage):
        return {"role": "tool", "content": message.content, "tool_call_id": message.tool_call_id}
    return {"role": "user", "content": str(message.content)}


def _usage_from_litellm_response(response: Any) -> dict[str, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    if isinstance(usage, dict):
        prompt = int(usage.get("prompt_tokens") or 0)
        completion = int(usage.get("completion_tokens") or 0)
    else:
        prompt = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion = int(getattr(usage, "completion_tokens", 0) or 0)
    total = int(getattr(usage, "total_tokens", 0) or prompt + completion)
    return {"prompt_tokens": prompt, "completion_tokens": completion, "total_tokens": total}


def _resolve_tool_calls(message: Any, content: str) -> list[dict[str, Any]]:
    native = litellm_tool_calls_to_langchain(getattr(message, "tool_calls", None))
    if native:
        return native
    return tool_calls_from_content(content)


def _message_chunk_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if content:
        return str(content)
    return ""


def _chat_result_from_litellm(response: Any) -> ChatResult:
    choice = response.choices[0]
    message = choice.message
    content = message.content or ""
    token_usage = _usage_from_litellm_response(response)
    usage_metadata = {
        "input_tokens": token_usage["prompt_tokens"],
        "output_tokens": token_usage["completion_tokens"],
        "total_tokens": token_usage["total_tokens"],
    }
    tool_calls = _resolve_tool_calls(message, content)
    ai_message = AIMessage(
        content=content,
        tool_calls=tool_calls,
        usage_metadata=usage_metadata,
    )
    return ChatResult(
        generations=[ChatGeneration(message=ai_message)],
        llm_output={"token_usage": token_usage},
    )


class LiteLLMChatModel(BaseChatModel):
    """Thin LangChain adapter over litellm.completion — no OpenAI SDK dependency."""

    model: str
    api_key: str | None = None
    api_base: str | None = None
    temperature: float = Field(default=0.1)
    request_timeout: float | None = None
    thinking_token_budget: int = Field(default=0)
    bound_tools: list[dict[str, Any]] | None = None
    bound_tool_choice: str | dict[str, Any] | None = None

    @property
    def _llm_type(self) -> str:
        return "litellm"

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable[..., Any] | BaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, AIMessage]:
        return self.model_copy(
            update={
                "bound_tools": tools_to_openai_schema(tools),
                "bound_tool_choice": _normalize_tool_choice(tool_choice),
            }
        )

    def _build_call_kwargs(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        normalized = normalize_messages_for_litellm(messages)
        litellm_messages = [_to_litellm_message(m) for m in normalized]
        call_kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": litellm_messages,
            "temperature": self.temperature,
        }
        if self.api_key:
            call_kwargs["api_key"] = self.api_key
        if self.api_base:
            call_kwargs["api_base"] = self.api_base
        if stop:
            call_kwargs["stop"] = stop
        if self.request_timeout is not None:
            call_kwargs["timeout"] = self.request_timeout
        if self.bound_tools:
            call_kwargs["tools"] = self.bound_tools
            choice = _normalize_tool_choice(self.bound_tool_choice)
            if choice is not None:
                call_kwargs["tool_choice"] = choice
        call_kwargs.update(kwargs)
        if self.thinking_token_budget > 0:
            extra_body = dict(call_kwargs.get("extra_body") or {})
            extra_body.setdefault("thinking_token_budget", self.thinking_token_budget)
            call_kwargs["extra_body"] = extra_body
        if call_kwargs.get("tools"):
            choice = _normalize_tool_choice(call_kwargs.get("tool_choice"))
            if choice is not None:
                call_kwargs["tool_choice"] = choice
            else:
                call_kwargs.pop("tool_choice", None)
        return call_kwargs

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        call_kwargs = self._build_call_kwargs(messages, stop, **kwargs)
        response = litellm.completion(**call_kwargs)
        return _chat_result_from_litellm(response)

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        call_kwargs = self._build_call_kwargs(messages, stop, **kwargs)
        response = await litellm.acompletion(**call_kwargs)
        return _chat_result_from_litellm(response)

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        call_kwargs = self._build_call_kwargs(messages, stop, **kwargs)
        call_kwargs["stream"] = True
        try:
            response = await litellm.acompletion(**call_kwargs)
        except Exception:
            result = await self._agenerate(messages, stop, run_manager=run_manager, **kwargs)
            generation = result.generations[0]
            message = generation.message
            if isinstance(message, AIMessage):
                chunk = AIMessageChunk(
                    content=_message_chunk_content(message.content),
                    tool_calls=message.tool_calls,
                )
            else:
                chunk = AIMessageChunk(content=str(getattr(generation, "text", "") or ""))
            yield ChatGenerationChunk(message=chunk)
            return

        async for raw_chunk in response:
            if not getattr(raw_chunk, "choices", None):
                continue
            delta = raw_chunk.choices[0].delta
            content = getattr(delta, "content", None) or ""
            tool_calls = getattr(delta, "tool_calls", None)
            if not content and not tool_calls:
                continue
            if content and run_manager is not None:
                await run_manager.on_llm_new_token(content)
            message_chunk = AIMessageChunk(content=content)
            if tool_calls:
                message_chunk.tool_call_chunks = tool_calls
            yield ChatGenerationChunk(message=message_chunk)


class LiteLLMProvider:
    """Default ChatModelProvider implementation."""

    def create(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str | None,
        temperature: float,
        request_timeout: float | None = None,
        thinking_token_budget: int = 0,
    ) -> BaseChatModel:
        import os

        if api_key:
            if model.startswith("deepseek/"):
                os.environ.setdefault("DEEPSEEK_API_KEY", api_key)
            elif model.startswith("openrouter/"):
                os.environ.setdefault("OPENROUTER_API_KEY", api_key)
            elif model.startswith("gemini/"):
                os.environ.setdefault("GEMINI_API_KEY", api_key)
        return LiteLLMChatModel(
            model=model,
            api_key=api_key or None,
            api_base=base_url or None,
            temperature=temperature,
            request_timeout=request_timeout,
            thinking_token_budget=thinking_token_budget,
        )
