from __future__ import annotations

from cys_core.application.ports.job_store import JobRecord, JobStorePort
from cys_core.infrastructure.job_store.factory import get_job_store
from cys_core.infrastructure.job_store.in_memory import InMemoryJobStore


class JobStore:
    """Isolated in-memory job store for tests and local dev."""

    def __init__(self) -> None:
        self._store: JobStorePort = InMemoryJobStore()

    def __getattr__(self, name: str):
        return getattr(self._store, name)


__all__ = ["JobRecord", "JobStore", "get_job_store"]
