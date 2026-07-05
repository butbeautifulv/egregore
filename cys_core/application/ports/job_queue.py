from __future__ import annotations

from typing import Protocol

from cys_core.application.ports.managed_resource import Closeable
from cys_core.domain.workers.models import WorkerJob


class JobQueueConnector(Closeable, Protocol):
    """Port for worker job queue."""

    name: str

    def enqueue(self, job: WorkerJob) -> str:
        """Enqueue worker job, return job id."""

    def dequeue(self, timeout: float = 0.0) -> WorkerJob | None:
        """Dequeue next job or None."""

    async def aenqueue(self, job: WorkerJob) -> str:
        """Async enqueue."""

    async def adequeue(self, timeout: float = 0.0) -> WorkerJob | None:
        """Async dequeue."""
