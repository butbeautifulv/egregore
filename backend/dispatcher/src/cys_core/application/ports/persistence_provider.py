from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cys_core.application.ports import PersistenceContext

_sync_persistence: Callable[[], PersistenceContext] | None = None
_async_persistence: Callable[[], Awaitable[PersistenceContext]] | None = None


def configure_persistence_providers(
    sync_fn: Callable[[], PersistenceContext],
    async_fn: Callable[[], Awaitable[PersistenceContext]],
) -> None:
    global _sync_persistence, _async_persistence
    _sync_persistence = sync_fn
    _async_persistence = async_fn


def get_sync_persistence() -> PersistenceContext:
    if _sync_persistence is None:
        raise RuntimeError("Persistence provider not configured")
    return _sync_persistence()


async def get_async_persistence() -> PersistenceContext:
    if _async_persistence is None:
        raise RuntimeError("Async persistence provider not configured")
    return await _async_persistence()
