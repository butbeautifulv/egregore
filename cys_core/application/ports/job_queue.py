from __future__ import annotations

from typing import Any, Protocol


class JobQueueConnector(Protocol):
    """Port for worker job queue."""

    name: str

    def enqueue(self, job: dict[str, Any]) -> str:
        """Enqueue worker job, return job id."""

    def dequeue(self, timeout: float = 0.0) -> dict[str, Any] | None:
        """Dequeue next job or None."""

    async def aenqueue(self, job: dict[str, Any]) -> str:
        """Async enqueue."""

    async def adequeue(self, timeout: float = 0.0) -> dict[str, Any] | None:
        """Async dequeue."""
