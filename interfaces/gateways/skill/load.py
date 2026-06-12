from __future__ import annotations

import re
from pathlib import Path

from cys_core.domain.security.content_delimiters import wrap_skill_content
from cys_core.domain.security.exceptions import SecurityViolation
from cys_core.domain.security.factory import get_input_sanitizer
from cys_core.domain.skills.models import SkillTrustTier
from cys_core.registry.skill_registry import SkillRegistry, compute_skill_hash, get_skill_registry
from interfaces.gateways.skill.audit import record_skill_load


class SkillLoadError(Exception):
    pass


def _read_skill_body(manifest_path: str) -> str:
    path = Path(manifest_path)
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.DOTALL)
        if match:
            return match.group(2).strip()
    return text.strip()


def load_skill(
    skill_name: str,
    *,
    persona: str,
    allowed_skills: list[str],
    registry: SkillRegistry | None = None,
    job_id: str = "",
) -> str:
    """Load skill body through gateway with allowlist, hash verify, and sanitization."""
    if skill_name not in allowed_skills:
        raise SkillLoadError(f"Skill '{skill_name}' not in persona allowlist")

    reg = registry or get_skill_registry()
    manifest = reg.get(skill_name)
    if manifest.trust_tier == SkillTrustTier.COMMUNITY:
        raise SkillLoadError("Community skill tier requires explicit privileged opt-in")

    body = _read_skill_body(manifest.path)
    actual_hash = compute_skill_hash(body)
    if manifest.content_hash and actual_hash != manifest.content_hash:
        raise SkillLoadError(f"Skill hash mismatch for '{skill_name}' — load rejected")

    sanitizer = get_input_sanitizer()
    try:
        sanitized = sanitizer.sanitize(body, source="skill")
    except SecurityViolation as exc:
        raise SkillLoadError(f"Poisoned skill body blocked: {exc}") from exc

    record_skill_load(
        skill_name=skill_name,
        persona=persona,
        content_hash=actual_hash,
        job_id=job_id,
        trust_tier=manifest.trust_tier.value,
    )
    return wrap_skill_content(sanitized)
