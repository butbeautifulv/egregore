from __future__ import annotations

from collections.abc import Callable

_catalog_singleton_rebind: Callable[[bool, bool], None] | None = None


def configure_catalog_singleton_rebind(fn: Callable[[bool, bool], None]) -> None:
    global _catalog_singleton_rebind
    _catalog_singleton_rebind = fn


def rebind_catalog_singletons_if_needed(*, prev_use_postgres: bool, new_use_postgres: bool) -> None:
    if _catalog_singleton_rebind is not None:
        _catalog_singleton_rebind(prev_use_postgres, new_use_postgres)
