from __future__ import annotations

import hashlib

from cys_core.infrastructure.skill.load_skill import SkillLoadError, load_skill as _load_skill

from .audit import record_skill_load

__all__ = ["SkillLoadError", "load_skill"]


def load_skill(
    skill_name: str,
    *,
    persona: str,
    allowed_skills: list[str],
    job_id: str = "",
    profile_id: str = "cybersec-soc",
) -> str:
    body = _load_skill(
        skill_name,
        persona=persona,
        allowed_skills=allowed_skills,
        job_id=job_id,
        profile_id=profile_id,
    )
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()[:12]
    record_skill_load(
        skill_name=skill_name,
        persona=persona,
        content_hash=digest,
        job_id=job_id,
    )
    return body
