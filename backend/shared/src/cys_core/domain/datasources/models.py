from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator

from cys_core.domain.security.data_classification import DataClassification


class DataSourceCapability(str, Enum):
    """Datasource access capability. Default policy is GET-only (list/get)."""

    GET = "get"
    LIST = "list"
    QUERY = "query"
    MUTATE = "mutate"


class DataSource(BaseModel):
    id: str
    type: str
    tenant_id: str = "default"
    enabled: bool = True
    connector_ref: str = ""
    capabilities: list[DataSourceCapability] = Field(
        default_factory=lambda: [DataSourceCapability.GET, DataSourceCapability.LIST],
    )
    allowed_roles: list[str] = Field(default_factory=list)
    classification: DataClassification = DataClassification.INTERNAL
    owner: str = ""

    @field_validator("capabilities")
    @classmethod
    def _default_get_only(cls, value: list[DataSourceCapability]) -> list[DataSourceCapability]:
        return value or [DataSourceCapability.GET, DataSourceCapability.LIST]
