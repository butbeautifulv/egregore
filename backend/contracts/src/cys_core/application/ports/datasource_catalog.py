from __future__ import annotations

import builtins
from typing import Protocol

from cys_core.domain.datasources.models import DataSource


class DataSourceCatalogPort(Protocol):
    """Port for datasource catalog CRUD (no credentials)."""

    def list(self, *, tenant_id: str | None = None, enabled_only: bool = True) -> builtins.list[DataSource]: ...

    def get(self, datasource_id: str) -> DataSource | None: ...

    def upsert(self, source: DataSource) -> DataSource: ...

    def seed(self, sources: builtins.list[DataSource]) -> int: ...
