from __future__ import annotations

from cys_core.infrastructure.engagement.memory_store import MemoryEngagementStateStore
from cys_core.infrastructure.engagement.postgres_store import PostgresEngagementStateStore
from cys_core.infrastructure.persistence_store_factory import resolve_persistence_store

_engagement_store = None


def _use_postgres_engagement_store(settings) -> bool:
    connector = settings.engagement_store_connector.lower()
    if connector == "memory":
        return False
    if connector == "postgres":
        return True
    return not settings.use_memory_fallback and settings.stage != "test"


def get_engagement_state_store(settings) -> MemoryEngagementStateStore | PostgresEngagementStateStore:
    global _engagement_store
    if _engagement_store is not None:
        return _engagement_store
    _engagement_store = resolve_persistence_store(
        settings,
        connector=settings.engagement_store_connector,
        use_postgres=_use_postgres_engagement_store,
        postgres_factory=PostgresEngagementStateStore,
        memory_factory=MemoryEngagementStateStore,
        fallback_label="engagement_state",
    )
    return _engagement_store


def reset_engagement_state_store() -> None:
    global _engagement_store
    _engagement_store = None
