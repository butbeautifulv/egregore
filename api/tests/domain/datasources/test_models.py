from __future__ import annotations

import pytest

from cys_core.domain.datasources.models import DataSource, DataSourceCapability
from cys_core.domain.datasources.validation import validate_datasource_capabilities
from cys_core.domain.security.data_classification import DataClassification


@pytest.mark.unit
def test_datasource_defaults_get_only() -> None:
    source = DataSource(id="siem-1", type="siem", tenant_id="default")
    assert DataSourceCapability.GET in source.capabilities
    assert DataSourceCapability.MUTATE not in source.capabilities


@pytest.mark.unit
def test_mutate_requires_get_capability() -> None:
    with pytest.raises(ValueError, match="mutate capability requires get"):
        validate_datasource_capabilities([DataSourceCapability.MUTATE])


@pytest.mark.unit
def test_datasource_round_trip() -> None:
    source = DataSource(
        id="rag-1",
        type="rag",
        classification=DataClassification.CONFIDENTIAL,
        allowed_roles=["reader"],
    )
    restored = DataSource.model_validate(source.model_dump())
    assert restored.id == "rag-1"
    assert restored.classification == DataClassification.CONFIDENTIAL
