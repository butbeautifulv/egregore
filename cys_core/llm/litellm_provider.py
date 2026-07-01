from __future__ import annotations

from typing import Any, Sequence

import litellm
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from pydantic import Field


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
        litellm_messages = [_to_litellm_message(m) for m in messages]
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
        choice = response.choices[0]
        content = choice.message.content or ""
        ai_message = AIMessage(content=content)
        return ChatResult(generations=[ChatGeneration(message=ai_message)])

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        litellm_messages = [_to_litellm_message(m) for m in messages]
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
        choice = response.choices[0]
        content = choice.message.content or ""
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])


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
