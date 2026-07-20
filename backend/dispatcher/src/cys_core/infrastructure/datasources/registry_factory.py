from __future__ import annotations

from cys_core.application.ports.datasource_catalog import DataSourceCatalogPort
from cys_core.infrastructure.datasources.memory import InMemoryDataSourceCatalog

_catalog: DataSourceCatalogPort | None = None


def get_datasource_catalog() -> DataSourceCatalogPort:
    global _catalog
    if _catalog is None:
        _catalog = InMemoryDataSourceCatalog()
    return _catalog


def reset_datasource_catalog_cache() -> None:
    global _catalog
    _catalog = None
