from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentConfig(BaseModel):
    """Parsed product agent.yaml configuration."""

    name: str
    description: str
    role: Literal["specialist", "critic", "coordinator"]
    output_schema: str | None = None
    tools: list[str] = Field(default_factory=list)
    hitl_tools: dict[str, bool] = Field(default_factory=dict)
    trust_level: str = "internal"
    bus_recipients: list[str] = Field(default_factory=list)
    language: str = "ru"
    sample: str = "samples/default.txt"
    interrupt_on: dict[str, bool] = Field(default_factory=dict)


class AgentDefinition(BaseModel):
    """Resolved agent definition ready for application services."""

    name: str
    description: str
    role: Literal["specialist", "critic", "coordinator"]
    system_prompt: str
    schema_name: str | None = None
    tools: list[str] = Field(default_factory=list)
    hitl_tools: dict[str, bool] = Field(default_factory=dict)
    trust_level: str = "internal"
    bus_recipients: list[str] = Field(default_factory=list)
    sample_input: str | None = None
    interrupt_on: dict[str, bool] = Field(default_factory=dict)
    skill_path: Path | None = None

    @property
    def allowed_tools(self) -> set[str]:
        return set(self.tools)

