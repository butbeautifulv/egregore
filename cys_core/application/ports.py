from __future__ import annotations

from typing import Any, Protocol


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

