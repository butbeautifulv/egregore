from __future__ import annotations

from cys_core.application.ports.datasource_catalog import DataSourceCatalogPort
from cys_core.domain.datasources.models import DataSource


class InMemoryDataSourceCatalog:
    def __init__(self) -> None:
        self._sources: dict[str, DataSource] = {}

    def list(self, *, tenant_id: str | None = None, enabled_only: bool = True) -> list[DataSource]:
        del tenant_id
        items = list(self._sources.values())
        if enabled_only:
            items = [item for item in items if item.enabled]
        return items

    def get(self, datasource_id: str) -> DataSource | None:
        return self._sources.get(datasource_id)

    def upsert(self, source: DataSource) -> DataSource:
        self._sources[source.id] = source
        return source

    def seed(self, sources: list[DataSource]) -> int:
        for source in sources:
            self.upsert(source)
        return len(sources)


_catalog = InMemoryDataSourceCatalog()


def get_datasource_catalog() -> DataSourceCatalogPort:
    return _catalog


def build_datasource_catalog_port() -> DataSourceCatalogPort:
    return get_datasource_catalog()
