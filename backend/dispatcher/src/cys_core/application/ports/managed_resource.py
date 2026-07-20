from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Closeable(Protocol):
    """Async cleanup for infrastructure adapters (Kafka, Redis, HTTP clients)."""

    async def aclose(self) -> None:
        """Release connections and background tasks deterministically."""


@runtime_checkable
class ManagedResource(Closeable, Protocol):
    """Named infrastructure connector with explicit lifecycle."""

    name: str
