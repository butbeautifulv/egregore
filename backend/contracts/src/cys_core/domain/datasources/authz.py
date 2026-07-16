from __future__ import annotations

from pydantic import BaseModel, Field

from cys_core.domain.datasources.models import DataSourceCapability


class AuthzRequest(BaseModel):
    persona: str
    profile_id: str
    tenant_id: str = "default"
    datasource_id: str
    capability: DataSourceCapability
    tool_name: str = ""


class AuthorizationDecision(BaseModel):
    allowed: bool
    reason: str
    tags: list[str] = Field(default_factory=list)
    matched_rule: str = ""
