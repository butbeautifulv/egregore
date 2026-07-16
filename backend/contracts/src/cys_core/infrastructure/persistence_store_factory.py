from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from cys_core.domain.persistence.exceptions import PersistenceUnavailableError
from cys_core.observability.metrics import metrics

T = TypeVar("T")


def resolve_persistence_store(
    settings: Any,
    *,
    connector: str | None,
    use_postgres: Callable[[Any], bool],
    postgres_factory: Callable[[str], T],
    memory_factory: Callable[[], T],
    fallback_label: str,
) -> T:
    """Shared postgres/memory selection with prod hard-fail and metrics fallback."""
    if connector and connector.lower() == "memory":
        return memory_factory()
    if connector and connector.lower() == "postgres":
        try:
            return postgres_factory(settings.postgres_url)
        except Exception as exc:
            if settings.stage == "prod" and not settings.use_memory_fallback:
                raise PersistenceUnavailableError(f"{fallback_label} unavailable") from exc
            metrics.record_persistence_fallback(fallback_label)
            return memory_factory()
    if use_postgres(settings):
        try:
            return postgres_factory(settings.postgres_url)
        except Exception as exc:
            if settings.stage == "prod" and not settings.use_memory_fallback:
                raise PersistenceUnavailableError(f"{fallback_label} unavailable") from exc
            metrics.record_persistence_fallback(fallback_label)
    return memory_factory()
