from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class Workspace(BaseModel):
    id: str
    organization_id: str = "default"
    name: str
    created_by: str = ""
    profile_id: str = "cybersec-soc"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    soft_deleted: bool = False


class WorkspaceAgent(BaseModel):
    """Forked worker persona scoped to a workspace."""

    workspace_id: str
    name: str
    source_agent: str
    persona_prompt: str = ""
    language: str = "ru"
    tools: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    description: str = ""
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
