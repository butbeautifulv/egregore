from __future__ import annotations

from typing import Any, Protocol

from langchain_core.language_models.chat_models import BaseChatModel


class ModelConnector(Protocol):
    """Port for swappable LLM/model backends."""

    name: str

    def create_model(self) -> BaseChatModel:
        """Create the configured chat model."""

    def callbacks(self) -> list[Any]:
        """Return optional tracing callbacks."""
