from __future__ import annotations

from typing import Any, Sequence

import litellm
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from pydantic import Field


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
                    "function": {"name": tc["name"], "arguments": tc.get("args", {})},
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


def _chat_result_from_litellm(response: Any) -> ChatResult:
    choice = response.choices[0]
    content = choice.message.content or ""
    token_usage = _usage_from_litellm_response(response)
    usage_metadata = {
        "input_tokens": token_usage["prompt_tokens"],
        "output_tokens": token_usage["completion_tokens"],
        "total_tokens": token_usage["total_tokens"],
    }
    ai_message = AIMessage(content=content, usage_metadata=usage_metadata)
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

    @property
    def _llm_type(self) -> str:
        return "litellm"

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | BaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> Runnable[Any, BaseMessage]:
        """LangChain agents require bind_tools; local vLLM uses prompt-based tool/schema flow."""
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
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
        call_kwargs.update(kwargs)

        response = litellm.completion(**call_kwargs)
        return _chat_result_from_litellm(response)

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
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
        call_kwargs.update(kwargs)

        response = await litellm.acompletion(**call_kwargs)
        return _chat_result_from_litellm(response)


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
    ) -> BaseChatModel:
        return LiteLLMChatModel(
            model=model,
            api_key=api_key or None,
            api_base=base_url or None,
            temperature=temperature,
            request_timeout=request_timeout,
        )
