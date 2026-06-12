from __future__ import annotations

from typing import Any

from bootstrap.settings import settings
from cys_core.application.ports import ModelConnector
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
    return get_model_connector().create_model()


def get_langfuse_callbacks() -> list[Any]:
    """Optional Langfuse tracing callbacks."""
    return get_model_connector().callbacks()


class LLMConnector:
    """ModelConnector implementation backed by configured ChatModelProvider."""

    def __init__(self, provider_name: str | None = None) -> None:
        self.name = provider_name or settings.llm_provider

    def create_model(self):
        provider = get_provider(self.name)
        return provider.create(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            temperature=settings.llm_temperature,
        )

    def callbacks(self) -> list[Any]:
        return _build_langfuse_callbacks()


_MODEL_CONNECTORS: dict[str, ModelConnector] = {
    "litellm": LLMConnector("litellm"),
}


def get_model_connector(name: str | None = None) -> ModelConnector:
    connector_name = name or settings.llm_provider
    if connector_name not in _MODEL_CONNECTORS:
        raise ValueError(f"Unknown model connector: {connector_name}")
    return _MODEL_CONNECTORS[connector_name]


def _build_langfuse_callbacks() -> list[Any]:
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
