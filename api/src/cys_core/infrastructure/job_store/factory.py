from __future__ import annotations

from cys_core.infrastructure.job_store.in_memory import InMemoryJobStore
from cys_core.infrastructure.job_store.postgres import PostgresJobStore
from cys_core.infrastructure.persistence_store_factory import resolve_persistence_store

_job_store = None


def _use_postgres_job_store(settings) -> bool:
    connector = settings.job_store_connector.lower()
    if connector == "memory":
        return False
    if connector == "postgres":
        return True
    return not settings.use_memory_fallback and settings.stage != "test"


def get_job_store(settings) -> InMemoryJobStore | PostgresJobStore:
    global _job_store
    if _job_store is not None:
        return _job_store
    _job_store = resolve_persistence_store(
        settings,
        connector=settings.job_store_connector,
        use_postgres=_use_postgres_job_store,
        postgres_factory=PostgresJobStore,
        memory_factory=InMemoryJobStore,
        fallback_label="job_store",
    )
    return _job_store


def reset_job_store() -> None:
    global _job_store
    _job_store = None
