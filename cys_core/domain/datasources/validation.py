from __future__ import annotations

from cys_core.domain.datasources.models import DataSource, DataSourceCapability
from cys_core.domain.security.data_classification import DataClassification

_CLASS_ORDER = [
    DataClassification.PUBLIC,
    DataClassification.INTERNAL,
    DataClassification.CONFIDENTIAL,
    DataClassification.RESTRICTED,
]


def capability_implies_write(capability: DataSourceCapability) -> bool:
    return capability in {DataSourceCapability.QUERY, DataSourceCapability.MUTATE}


def validate_datasource_capabilities(capabilities: list[DataSourceCapability]) -> None:
    if not capabilities:
        raise ValueError("datasource must expose at least one capability")
    if DataSourceCapability.MUTATE in capabilities and DataSourceCapability.GET not in capabilities:
        raise ValueError("mutate capability requires get capability")


def classification_allows(
    persona_clearance: DataClassification,
    datasource_classification: DataClassification,
) -> bool:
    return _CLASS_ORDER.index(datasource_classification) <= _CLASS_ORDER.index(persona_clearance)


def validate_datasource(source: DataSource) -> None:
    validate_datasource_capabilities(source.capabilities)
