from __future__ import annotations

from typing import Any, Protocol

from langchain_core.language_models.chat_models import BaseChatModel


class PersistenceContext(Protocol):
    """Storage-agnostic persistence context used by application services."""

    checkpointer: Any
    store: Any


class PersistenceConnector(Protocol):
    """Port for sync and async persistence connectors."""

    name: str

    def open(self, *, force_memory: bool | None = None) -> PersistenceContext:
        """Open a sync persistence context."""

    async def open_async(self, *, force_memory: bool | None = None) -> PersistenceContext:
        """Open an async persistence context."""


class ModelConnector(Protocol):
    """Port for swappable LLM/model backends."""

    name: str

    def create_model(self) -> BaseChatModel:
        """Create the configured chat model."""

    def callbacks(self) -> list[Any]:
        """Return optional tracing callbacks."""


class AgentTransportConnector(Protocol):
    """Port for inter-agent transport connectors."""

    name: str
    requires_mtls: bool

    def send(self, message: dict[str, Any]) -> dict[str, Any]:
        """Send an A2A message over the connector."""

    async def send_async(self, message: dict[str, Any]) -> dict[str, Any]:
        """Send an A2A message over the connector asynchronously."""

