from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Sequence
from typing import Any

from langchain_core.language_models import LanguageModelInput
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from pydantic import Field

from cys_core.infrastructure.http_client import async_http_client, sync_http_client
from cys_core.llm.litellm_provider import (
    _normalize_tool_choice,
    _serialize_tool_arguments,
    normalize_messages_for_litellm,
    tools_to_openai_schema,
)
from cys_core.llm.tool_call_parsing import litellm_tool_calls_to_langchain


def _to_gateway_message(message: BaseMessage) -> dict[str, Any]:
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


def _usage_metadata(usage: dict[str, Any]) -> dict[str, int]:
    prompt = int(usage.get("prompt_tokens", 0) or 0)
    completion = int(usage.get("completion_tokens", 0) or 0)
    total = int(usage.get("total_tokens", 0) or prompt + completion)
    return {"input_tokens": prompt, "output_tokens": completion, "total_tokens": total}


def _chat_result_from_gateway_response(data: dict[str, Any]) -> ChatResult:
    if not data.get("success", True):
        raise RuntimeError(data.get("error") or "model-gateway invoke failed")
    content = data.get("content", "") or ""
    tool_calls = litellm_tool_calls_to_langchain(data.get("tool_calls") or [])
    ai_message = AIMessage(
        content=content,
        tool_calls=tool_calls,
        usage_metadata=_usage_metadata(data.get("usage") or {}),
    )
    return ChatResult(generations=[ChatGeneration(message=ai_message)])


class ModelGatewayChatModel(BaseChatModel):
    """LangChain adapter that routes chat completions through model-gateway's
    POST /v1/model/invoke instead of calling litellm directly — the model-layer half
    of "switch core to any agent on the market, inside a safe system" (docs/
    MSP_BACKLOG.md §29, plan §1 item 2). PromptContextMiddleware already sanitizes
    messages and stamps GLOBAL_RULES:/SECURITY_RULES: markers before this class ever
    sees them; model-gateway re-checks both independently (defense-in-depth, same
    "keep both" call §29.4 made explicit for tool-gateway's equivalent case)."""

    model: str
    gateway_url: str
    shared_secret: str = ""
    persona: str = "agent-runtime"
    temperature: float = Field(default=0.1)
    request_timeout: float | None = None
    bound_tools: list[dict[str, Any]] | None = None
    bound_tool_choice: str | dict[str, Any] | None = None

    @property
    def _llm_type(self) -> str:
        return "model-gateway"

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

    def _build_request_body(self, messages: list[BaseMessage]) -> dict[str, Any]:
        normalized = normalize_messages_for_litellm(messages)
        system_prompt = ""
        rest = normalized
        if normalized and isinstance(normalized[0], SystemMessage):
            system_prompt = str(normalized[0].content)
            rest = normalized[1:]
        body: dict[str, Any] = {
            "persona": self.persona,
            "system_prompt": system_prompt,
            "messages": [_to_gateway_message(m) for m in rest],
            "model": self.model,
            "temperature": self.temperature,
        }
        if self.bound_tools:
            body["tools"] = self.bound_tools
            choice = _normalize_tool_choice(self.bound_tool_choice)
            if choice is not None:
                body["tool_choice"] = choice
        return body

    def _headers(self) -> dict[str, str]:
        if self.shared_secret:
            return {"Authorization": f"Bearer {self.shared_secret}"}
        return {}

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        body = self._build_request_body(messages)
        with sync_http_client(timeout=self.request_timeout, headers=self._headers()) as client:
            response = client.post(f"{self.gateway_url}/v1/model/invoke", json=body)
            response.raise_for_status()
            data = response.json()
        return _chat_result_from_gateway_response(data)

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        body = self._build_request_body(messages)
        async with async_http_client(timeout=self.request_timeout, headers=self._headers()) as client:
            response = await client.post(f"{self.gateway_url}/v1/model/invoke", json=body)
            response.raise_for_status()
            data = response.json()
        return _chat_result_from_gateway_response(data)

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        # model-gateway has no streaming endpoint yet (docs/MSP_BACKLOG.md §29.4) — same
        # one-shot-chunk shape LiteLLMChatModel._astream already falls back to on error.
        result = await self._agenerate(messages, stop, run_manager=run_manager, **kwargs)
        generation = result.generations[0]
        message = generation.message
        if isinstance(message, AIMessage):
            chunk = AIMessageChunk(content=str(message.content or ""), tool_calls=message.tool_calls)
        else:
            chunk = AIMessageChunk(content=str(getattr(generation, "text", "") or ""))
        yield ChatGenerationChunk(message=chunk)


class ModelGatewayProvider:
    """ChatModelProvider (cys_core.llm.protocol) backed by model-gateway instead of a
    direct litellm call. Registered under the "model-gateway" name in cys_core/llm/
    __init__.py's _PROVIDERS/_MODEL_CONNECTORS — select it via the MODEL_PROVIDER
    setting, same seam AGENT_RUNNER_IMPL uses one layer up."""

    def __init__(self, *, gateway_url: str, shared_secret: str = "") -> None:
        self._gateway_url = gateway_url.rstrip("/")
        self._shared_secret = shared_secret

    def create(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str | None,
        temperature: float,
        request_timeout: float | None = None,
        thinking_token_budget: int = 0,
        num_retries: int = 0,
    ) -> BaseChatModel:
        return ModelGatewayChatModel(
            model=model,
            gateway_url=self._gateway_url,
            shared_secret=self._shared_secret,
            temperature=temperature,
            request_timeout=request_timeout,
        )
