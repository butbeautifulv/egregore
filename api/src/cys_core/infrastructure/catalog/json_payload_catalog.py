from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Generic, Protocol, TypeVar

from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID


class _PayloadEntry(Protocol):
    id: str
    profile_id: str
    enabled: bool


T = TypeVar("T", bound=_PayloadEntry)


class JsonPayloadCatalog(Generic[T]):
    """In-memory JSON-payload catalog keyed by (id, profile_id)."""

    def __init__(self, *, sort_key: Callable[[T], object] | None = None) -> None:
        self._items: dict[tuple[str, str], T] = {}
        self._lock = threading.Lock()
        self._sort_key = sort_key or (lambda item: item.id)

    @staticmethod
    def item_key(entry: T) -> tuple[str, str]:
        return (entry.id, entry.profile_id)

    def list_items(
        self, *, profile_id: str | None = None, enabled_only: bool = True
    ) -> list[T]:
        with self._lock:
            items = list(self._items.values())
        if profile_id:
            items = [item for item in items if item.profile_id == profile_id]
        if enabled_only:
            items = [item for item in items if item.enabled]
        return sorted(items, key=lambda item: str(self._sort_key(item)))

    def get_item(self, item_id: str, *, profile_id: str = DEFAULT_PROFILE_ID) -> T | None:
        with self._lock:
            return self._items.get((item_id, profile_id))

    def upsert_item(
        self,
        entry: T,
        *,
        merge: Callable[[T, T], None] | None = None,
    ) -> T:
        with self._lock:
            key = self.item_key(entry)
            existing = self._items.get(key)
            if existing is not None and merge is not None:
                merge(entry, existing)
            self._items[key] = entry
            return entry

    def soft_delete(self, item_id: str, *, profile_id: str = DEFAULT_PROFILE_ID) -> bool:
        with self._lock:
            entry = self._items.get((item_id, profile_id))
            if entry is None:
                return False
            entry.enabled = False
            return True

    def seed_items(self, entries: list[T]) -> None:
        with self._lock:
            for entry in entries:
                self._items[self.item_key(entry)] = entry
