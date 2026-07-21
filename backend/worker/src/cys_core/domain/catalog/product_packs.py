from __future__ import annotations

from pydantic import BaseModel, Field


class EvalPack(BaseModel):
    """Domain-specific evaluation suite configuration."""

    id: str
    suite: str = "default"
    metrics: list[str] = Field(default_factory=list)
    thresholds: dict[str, float] = Field(default_factory=dict)
    benchmark_profile: str = ""


class PersonaPack(BaseModel):
    """Catalog-facing persona reference within a product pack."""

    id: str
    name: str
    role: str = "worker"
    catalog_agent: str
    enabled: bool = True
    tags: list[str] = Field(default_factory=list)


class DomainPack(BaseModel):
    """Domain taxonomy and adapter hooks for a product."""

    id: str
    name: str
    description: str = ""
    event_adapters: list[str] = Field(default_factory=list)
    default_plan: str = ""
    routing_event_types: list[str] = Field(default_factory=list)


class ProductProfilePack(BaseModel):
    """Top-level product definition bound to a catalog profile."""

    id: str
    name: str
    description: str = ""
    profile_id: str
    domains: list[DomainPack] = Field(default_factory=list)
    personas: list[PersonaPack] = Field(default_factory=list)
    eval_pack: EvalPack | None = None
    seed_module: str = ""
    tool_domains: list[str] = Field(default_factory=list)
