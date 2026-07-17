from __future__ import annotations

import warnings

from cys_core.application.ports.memory import EpisodicMemoryStore, InvestigationStateStore
from cys_core.infrastructure.memory.stores import (
    InMemoryEpisodicMemoryStore,
    InMemoryInvestigationStateStore,
    PostgresEpisodicMemoryStore,
    PostgresInvestigationStateStore,
)
from cys_core.infrastructure.persistence_store_factory import resolve_persistence_store

_episodic_store: EpisodicMemoryStore | None = None
_investigation_store: InvestigationStateStore | None = None
_memory_read_service = None
_memory_write_service = None


def _use_postgres_memory(settings) -> bool:
    return not settings.use_memory_fallback and settings.stage != "test"


def get_episodic_memory_store(settings) -> EpisodicMemoryStore:
    global _episodic_store
    if _episodic_store is not None:
        return _episodic_store
    _episodic_store = resolve_persistence_store(
        settings,
        connector=None,
        use_postgres=_use_postgres_memory,
        postgres_factory=PostgresEpisodicMemoryStore,
        memory_factory=InMemoryEpisodicMemoryStore,
        fallback_label="episodic_memory",
    )
    return _episodic_store


def get_investigation_state_store(settings) -> InvestigationStateStore:
    warnings.warn(
        "InvestigationStateStore is deprecated; use EngagementStateStore",
        DeprecationWarning,
        stacklevel=2,
    )
    global _investigation_store
    if _investigation_store is not None:
        return _investigation_store
    _investigation_store = resolve_persistence_store(
        settings,
        connector=None,
        use_postgres=_use_postgres_memory,
        postgres_factory=PostgresInvestigationStateStore,
        memory_factory=InMemoryInvestigationStateStore,
        fallback_label="investigation_state",
    )
    return _investigation_store


def reset_memory_stores() -> None:
    """Clear singletons — for tests."""
    global _episodic_store, _investigation_store, _memory_read_service, _memory_write_service
    _episodic_store = None
    _investigation_store = None
    _memory_read_service = None
    _memory_write_service = None


def get_memory_write_service(settings):
    global _memory_write_service
    if _memory_write_service is None:
        from cys_core.domain.memory.services import MemoryWriteService

        _memory_write_service = MemoryWriteService(get_episodic_memory_store(settings))
    return _memory_write_service


def get_memory_read_service(settings):
    global _memory_read_service
    if _memory_read_service is None:
        from cys_core.domain.memory.services import MemoryReadService

        _memory_read_service = MemoryReadService(get_episodic_memory_store(settings))
    return _memory_read_service
