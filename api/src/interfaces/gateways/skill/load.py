from __future__ import annotations

import hashlib

from cys_core.infrastructure.skill.load_skill import SkillLoadError
from cys_core.infrastructure.skill.load_skill import load_skill as _load_skill
from cys_core.registry.skill_registry import SkillRegistry

from .audit import record_skill_load

__all__ = ["SkillLoadError", "load_skill"]


def load_skill(
    skill_name: str,
    *,
    persona: str,
    allowed_skills: list[str],
    job_id: str = "",
    profile_id: str = "cybersec-soc",
    registry: SkillRegistry | None = None,
) -> str:
    body = _load_skill(
        skill_name,
        persona=persona,
        allowed_skills=allowed_skills,
        job_id=job_id,
        profile_id=profile_id,
        registry=registry,
    )
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()[:12]
    record_skill_load(
        skill_name=skill_name,
        persona=persona,
        content_hash=digest,
        job_id=job_id,
    )
    return body
