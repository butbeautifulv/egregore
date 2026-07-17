from __future__ import annotations

from pydantic import BaseModel, Field

from cys_core.domain.datasources.models import DataSourceCapability


class ToolDataSourceBinding(BaseModel):
    """Maps a gateway tool to a datasource capability requirement."""

    tool_name: str
    datasource_id: str
    capability: DataSourceCapability = DataSourceCapability.GET
    description: str = ""


class DataSourceDenyPayload(BaseModel):
    """Stable deny shape for gateway and audit consumers."""

    code: str = "datasource_denied"
    reason: str
    matched_rule: str = ""
    tags: list[str] = Field(default_factory=list)
    datasource_id: str = ""
    capability: str = ""
    tool_name: str = ""
    profile_id: str = ""
