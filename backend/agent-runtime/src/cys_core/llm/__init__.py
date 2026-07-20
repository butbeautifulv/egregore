from __future__ import annotations

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel

from cys_core.application.ports import ModelConnector
from cys_core.application.ports.trace_callbacks import get_trace_callbacks
from cys_core.application.runtime_config import get_default_job_recursion_limit, get_recursion_limit_for_persona
from cys_core.llm.litellm_provider import LiteLLMProvider
from cys_core.llm.protocol import ChatModelProvider

_PROVIDER_NAME = "litellm"

# "model-gateway" is registered here as a name only (ModelConnector doesn't read
# settings or import bootstrap — see LLMConnector below) but its ChatModelProvider
# instance is NOT constructed in this module: cys_core may never import
# bootstrap.settings outside the shrink-only ALLOWLIST_BOOTSTRAP_INTERFACES
# (scripts/verify_import_boundaries.py), same reasoning bootstrap/lazy_agent_runner.py
# documents for the AgentRunner registry one layer down. bootstrap/container.py's
# _wire_llm_provider() calls configure_llm_provider("model-gateway", ...) with a real
# ModelGatewayProvider(gateway_url=..., shared_secret=...) at Container construction
# time, before anything can actually call get_provider("model-gateway").
_PROVIDERS: dict[str, ChatModelProvider] = {
    _PROVIDER_NAME: LiteLLMProvider(),
}


def configure_llm_provider(name: str, provider: ChatModelProvider) -> None:
    _PROVIDERS[name] = provider


def configure_default_llm_provider(name: str) -> None:
    """Switch which provider get_provider()/get_model_connector() resolve to when
    called with no explicit name — the bootstrap-time selector driven by the
    MODEL_PROVIDER setting, mirrors cys_core.runtime.agent's AGENT_RUNNER_IMPL seam."""
    global _PROVIDER_NAME
    if name not in _PROVIDERS:
        raise ValueError(f"Unknown LLM provider: {name}")
    _PROVIDER_NAME = name


def get_provider(name: str | None = None) -> ChatModelProvider:
    provider_name = name or _PROVIDER_NAME
    if provider_name not in _PROVIDERS:
        raise ValueError(f"Unknown LLM provider: {provider_name}")
    return _PROVIDERS[provider_name]


def get_model() -> BaseChatModel:
    """Return configured chat model via selected provider."""
    return get_model_connector().create_model()


def get_langfuse_callbacks() -> list[Any]:
    """Optional Langfuse tracing callbacks."""
    return get_model_connector().callbacks()


class LLMConnector:
    """ModelConnector implementation backed by configured ChatModelProvider."""

    def __init__(self, provider_name: str | None = None) -> None:
        self.name = provider_name or _PROVIDER_NAME

    def create_model(self) -> BaseChatModel:
        from cys_core.application.runtime_config import get_llm_settings

        llm = get_llm_settings()
        provider = get_provider(self.name)
        return provider.create(
            model=llm["model"],
            api_key=llm["api_key"],
            base_url=llm["base_url"],
            temperature=llm["temperature"],
            request_timeout=llm["request_timeout"],
            thinking_token_budget=llm["thinking_token_budget"],
            num_retries=llm["num_retries"],
        )

    def callbacks(self) -> list[Any]:
        return get_trace_callbacks()


_MODEL_CONNECTORS: dict[str, ModelConnector] = {
    "litellm": LLMConnector("litellm"),
    "model-gateway": LLMConnector("model-gateway"),
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
