from __future__ import annotations

from cys_core.domain.datasources.models import DataSource
from cys_core.infrastructure.datasources.memory import InMemoryDataSourceCatalog


class CatalogBackedDataSourceCatalog(InMemoryDataSourceCatalog):
    """Placeholder for Postgres/catalog-backed datasource registry (Stream E)."""

    name = "catalog_skeleton"

    def list(self, *, tenant_id: str | None = None, enabled_only: bool = True) -> list[DataSource]:
        # Future: read from dynamic catalog tables.
        return super().list(tenant_id=tenant_id, enabled_only=enabled_only)
