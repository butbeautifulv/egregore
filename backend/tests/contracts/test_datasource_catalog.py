from __future__ import annotations

import pytest

from cys_core.domain.datasources.models import DataSource
from cys_core.infrastructure.datasources.memory import InMemoryDataSourceCatalog


@pytest.mark.unit
def test_inmemory_datasource_catalog_seed_and_get() -> None:
    catalog = InMemoryDataSourceCatalog()
    catalog.seed([DataSource(id="siem", type="siem")])
    assert catalog.get("siem") is not None
    assert len(catalog.list()) == 1
