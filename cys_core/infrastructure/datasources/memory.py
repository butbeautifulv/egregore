from __future__ import annotations

from cys_core.domain.datasources.models import DataSource
from cys_core.domain.datasources.validation import validate_datasource


class InMemoryDataSourceCatalog:
    """Dict-backed datasource catalog for tests and dev."""

    name = "memory"

    def __init__(self) -> None:
        self._sources: dict[str, DataSource] = {}

    def list(self, *, tenant_id: str | None = None, enabled_only: bool = True) -> list[DataSource]:
        items = list(self._sources.values())
        if tenant_id is not None:
            items = [s for s in items if s.tenant_id == tenant_id]
        if enabled_only:
            items = [s for s in items if s.enabled]
        return sorted(items, key=lambda s: s.id)

    def get(self, datasource_id: str) -> DataSource | None:
        return self._sources.get(datasource_id)

    def upsert(self, source: DataSource) -> DataSource:
        validate_datasource(source)
        self._sources[source.id] = source
        return source

    def seed(self, sources: list[DataSource]) -> int:
        for source in sources:
            self.upsert(source)
        return len(sources)
