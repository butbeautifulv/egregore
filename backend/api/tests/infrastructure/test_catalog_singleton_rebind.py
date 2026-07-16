from __future__ import annotations

from bootstrap.container import Container
from cys_core.application.catalog_singletons import rebind_catalog_singletons_if_needed
from cys_core.infrastructure.catalog.catalog_singletons import CatalogSingletons
from cys_core.infrastructure.catalog.memory_tools import InMemoryToolCatalog
from cys_core.infrastructure.catalog.registry_factory import get_tool_catalog, reset_catalog_singletons


def test_rebind_clears_tool_catalog_singleton_when_postgres_mode_enables() -> None:
    reset_catalog_singletons()
    polluted = get_tool_catalog()
    assert isinstance(polluted, InMemoryToolCatalog)

    Container._wire_catalog_singleton_rebind()
    rebind_catalog_singletons_if_needed(prev_use_postgres=False, new_use_postgres=True)

    rebound = get_tool_catalog()
    assert rebound is not polluted


def test_rebind_noop_when_backend_mode_unchanged() -> None:
    reset_catalog_singletons()
    instance = CatalogSingletons.get("tool_catalog", InMemoryToolCatalog)

    Container._wire_catalog_singleton_rebind()
    rebind_catalog_singletons_if_needed(prev_use_postgres=True, new_use_postgres=True)

    assert CatalogSingletons.get("tool_catalog", InMemoryToolCatalog) is instance
