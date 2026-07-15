from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class SkillTrustTier(str, Enum):
    BUILTIN = "builtin"
    VERIFIED = "verified"
    COMMUNITY = "community"


class SkillManifest(BaseModel):
    """Resolved builtin skill metadata from agents/skills/."""

    skill_id: str
    name: str
    description: str = ""
    version: str = "1.0.0"
    content_hash: str = ""
    trust_tier: SkillTrustTier = SkillTrustTier.BUILTIN
    path: str = ""
    author: str = "cys-agi"
    allowed_personas: list[str] = Field(default_factory=list)
