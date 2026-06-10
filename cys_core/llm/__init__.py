from __future__ import annotations

from typing import Any

from config import settings
from cys_core.llm.litellm_provider import LiteLLMProvider
from cys_core.llm.protocol import ChatModelProvider

_PROVIDERS: dict[str, ChatModelProvider] = {
    "litellm": LiteLLMProvider(),
}


def get_provider(name: str | None = None) -> ChatModelProvider:
    provider_name = name or settings.llm_provider
    if provider_name not in _PROVIDERS:
        raise ValueError(f"Unknown LLM provider: {provider_name}")
    return _PROVIDERS[provider_name]


def get_model():
    """Return configured chat model via selected provider."""
    provider = get_provider()
    return provider.create(
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        temperature=settings.llm_temperature,
    )


def get_langfuse_callbacks() -> list[Any]:
    """Optional Langfuse tracing callbacks."""
    if not settings.langfuse_api_key:
        return []
    try:
        from langfuse.langchain import CallbackHandler

        return [
            CallbackHandler(
                public_key=settings.langfuse_api_key,
                host=settings.langfuse_host,
            )
        ]
    except Exception:
        return []
