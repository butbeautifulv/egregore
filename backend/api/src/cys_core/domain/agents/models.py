from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from cys_core.domain.reasoning.sgr_models import SgrMode


class AgentConfig(BaseModel):
    """Parsed product agent.yaml configuration."""

    name: str
    description: str
    role: Literal["worker", "control", "specialist", "critic", "coordinator"]
    output_schema: str | None = None
    tools: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    hitl_tools: dict[str, bool] = Field(default_factory=dict)
    hitl_auto_approve: bool = False
    trust_level: str = "internal"
    bus_recipients: list[str] = Field(default_factory=list)
    language: str = "ru"
    sample: str = "samples/default.txt"
    interrupt_on: dict[str, bool] = Field(default_factory=dict)
    capabilities: list[str] = Field(default_factory=list)
    reasoning_mode: SgrMode = "off"


class AgentDefinition(BaseModel):
    """Resolved agent definition ready for application services."""

    name: str
    description: str
    role: Literal["worker", "control", "specialist", "critic", "coordinator"]
    system_prompt: str
    system_prompt_digest: str = ""
    persona_prompt: str = ""
    language: str = "ru"
    schema_name: str | None = None
    tools: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    hitl_tools: dict[str, bool] = Field(default_factory=dict)
    hitl_auto_approve: bool = False
    trust_level: str = "internal"
    bus_recipients: list[str] = Field(default_factory=list)
    sample_input: str | None = None
    interrupt_on: dict[str, bool] = Field(default_factory=dict)
    skill_path: Path | None = None
    capabilities: list[str] = Field(default_factory=list)
    reasoning_mode: SgrMode = "off"

    @property
    def allowed_tools(self) -> set[str]:
        return set(self.tools)
