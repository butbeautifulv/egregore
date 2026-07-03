from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from cys_core.domain.catalog.models import ProfilePack


class DomainPack(BaseModel):
    """Product-facing domain taxonomy + adapter config.

    Master-plan note: this is intentionally a lightweight skeleton that lets the
    platform *name* domains without hard-coding SOC semantics into core models.
    """

    id: str
    name: str = ""
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    adapter_config: dict[str, Any] = Field(default_factory=dict)


class PersonaPack(BaseModel):
    """A named bundle of personas for a product/domain."""

    id: str
    personas: list[str] = Field(default_factory=list)
    description: str = ""


class EvalPack(BaseModel):
    """A named bundle of eval suites/config for a product/domain."""

    id: str
    suites: list[str] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)


class ProductProfilePack(BaseModel):
    """Top-level product bundle.

    This wraps existing `ProfilePack` so current catalog + policy plumbing stays
    backward-compatible while we migrate from single-product SOC defaults.
    """

    id: str
    name: str
    version: str = "0.1.0"
    description: str = ""

    profiles: list[ProfilePack] = Field(default_factory=list)
    domains: list[DomainPack] = Field(default_factory=list)
    personas: list[PersonaPack] = Field(default_factory=list)
    evals: list[EvalPack] = Field(default_factory=list)

    default_profile_id: str = ""

    def resolve_default_profile_id(self) -> str:
        if self.default_profile_id:
            return self.default_profile_id
        if self.profiles:
            return self.profiles[0].id
        return ""

