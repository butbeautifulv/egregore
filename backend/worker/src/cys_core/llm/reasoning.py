from __future__ import annotations

from functools import lru_cache
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel

from cys_core.application.ports import ModelConnector
from cys_core.application.runtime_config import get_reasoning_llm_settings
from cys_core.llm import get_provider


class ReasoningModelConnector:
    """Separate connector for hints, trace critic, and GAIA extraction passes."""

    name = "litellm-reasoning"

    def create_model(self) -> BaseChatModel:
        settings = get_reasoning_llm_settings()
        provider = get_provider("litellm")
        return provider.create(
            model=settings["model"],
            api_key=settings["api_key"],
            base_url=settings["base_url"],
            temperature=settings["temperature"],
            request_timeout=settings["request_timeout"],
            thinking_token_budget=settings["thinking_token_budget"],
            num_retries=settings["num_retries"],
        )

    def callbacks(self) -> list[Any]:
        from cys_core.application.ports.trace_callbacks import get_trace_callbacks

        return get_trace_callbacks()


@lru_cache
def get_reasoning_model_connector() -> ModelConnector:
    return ReasoningModelConnector()
