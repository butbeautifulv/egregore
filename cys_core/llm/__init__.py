from __future__ import annotations

from typing import Any

from cys_core.application.ports.trace_callbacks import get_trace_callbacks
from cys_core.application.ports import ModelConnector
from cys_core.application.runtime_config import get_default_job_recursion_limit, get_recursion_limit_for_persona
from cys_core.llm.litellm_provider import LiteLLMProvider
from cys_core.llm.protocol import ChatModelProvider

_PROVIDER_NAME = "litellm"
_PROVIDERS: dict[str, ChatModelProvider] = {
    _PROVIDER_NAME: LiteLLMProvider(),
}


def configure_llm_provider(name: str, provider: ChatModelProvider) -> None:
    _PROVIDERS[name] = provider


def get_provider(name: str | None = None) -> ChatModelProvider:
    provider_name = name or _PROVIDER_NAME
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
        self.name = provider_name or _PROVIDER_NAME

    def create_model(self):
        from cys_core.application.runtime_config import get_llm_settings

        llm = get_llm_settings()
        provider = get_provider(self.name)
        return provider.create(
            model=llm["model"],
            api_key=llm["api_key"],
            base_url=llm["base_url"],
            temperature=llm["temperature"],
            request_timeout=llm["request_timeout"],
        )

    def callbacks(self) -> list[Any]:
        return get_trace_callbacks()


_MODEL_CONNECTORS: dict[str, ModelConnector] = {
    "litellm": LLMConnector("litellm"),
}


def get_model_connector(name: str | None = None) -> ModelConnector:
    connector_name = name or _PROVIDER_NAME
    if connector_name not in _MODEL_CONNECTORS:
        raise ValueError(f"Unknown model connector: {connector_name}")
    return _MODEL_CONNECTORS[connector_name]


def get_default_recursion_limit() -> int:
    return get_default_job_recursion_limit()


def get_persona_recursion_limit(persona: str) -> int:
    return get_recursion_limit_for_persona(persona)
