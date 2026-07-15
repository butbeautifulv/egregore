from __future__ import annotations

import hashlib
from pathlib import Path

from cys_core.application.runtime_config import get_use_dynamic_catalog
from cys_core.application.skills.catalog import skills_root
from cys_core.domain.catalog.models import StagingStatus
from cys_core.domain.security.factory import get_input_sanitizer
from cys_core.infrastructure.catalog.registry_factory import get_skill_catalog


class SkillLoadError(Exception):
    pass


def _skill_path(skill_name: str) -> Path:
    path = skills_root() / skill_name / "SKILL.md"
    if not path.is_file():
        raise SkillLoadError(f"Unknown skill: {skill_name}")
    return path


def _load_from_catalog(skill_name: str, *, profile_id: str = "cybersec-soc") -> str | None:
    if not get_use_dynamic_catalog():
        return None
    entry = get_skill_catalog().get_skill(skill_name, profile_id=profile_id)
    if entry is None or not entry.enabled:
        return None
    if entry.staging_status == StagingStatus.DRAFT:
        raise SkillLoadError(f"Skill '{skill_name}' is draft — approve before load")
    return entry.body


def load_skill(
    skill_name: str,
    *,
    persona: str,
    allowed_skills: list[str],
    job_id: str = "",
    profile_id: str = "cybersec-soc",
) -> str:
    if skill_name not in allowed_skills and allowed_skills:
        raise SkillLoadError(f"Skill '{skill_name}' not allowlisted for persona '{persona}'")
    body = _load_from_catalog(skill_name, profile_id=profile_id)
    if body is None:
        path = _skill_path(skill_name)
        body = path.read_text(encoding="utf-8")
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()[:12]
    sanitizer = get_input_sanitizer()
    safe = sanitizer.sanitize(body, source="skill")
    header = f"<!-- skill:{skill_name} sha:{digest} persona:{persona} job:{job_id} -->\n"
    try:
        catalog = get_skill_catalog()
        if hasattr(catalog, "increment_usage"):
            catalog.increment_usage(skill_name, profile_id=profile_id, error=False)
    except Exception:
        pass
    return header + safe
