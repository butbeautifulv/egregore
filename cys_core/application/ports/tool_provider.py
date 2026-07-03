from __future__ import annotations

from enum import Enum
from typing import Any, Protocol

from pydantic import BaseModel, Field


class ToolStatus(str, Enum):
    REAL = "real"
    SIMULATED = "simulated"
    STUB = "stub"
    DISABLED = "disabled"


class ToolDefinitionView(BaseModel):
    """Metadata surface for registries, schema export, docs generation, and evals."""

    name: str
    description: str = ""
    status: ToolStatus = ToolStatus.REAL
    risk_tier: str = "medium"
    tags: list[str] = Field(default_factory=list)
    json_schema: dict[str, Any] = Field(default_factory=dict)


class ToolProviderPort(Protocol):
    """Provides tool definitions + concrete tool objects for a profile/persona."""

    def list_definitions(self, *, profile_id: str) -> list[ToolDefinitionView]: ...

    def resolve(self, tool_names: list[str], *, profile_id: str) -> list[Any]: ...

