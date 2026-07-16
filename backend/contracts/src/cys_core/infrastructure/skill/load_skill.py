from __future__ import annotations

import hashlib
import re
from pathlib import Path

import yaml

from cys_core.application.runtime_config import get_use_dynamic_catalog
from cys_core.application.skills.catalog import skills_root
from cys_core.domain.catalog.models import StagingStatus
from cys_core.domain.security.factory import get_input_sanitizer
from cys_core.infrastructure.catalog.registry_factory import get_skill_catalog
from cys_core.registry.skill_registry import SkillRegistry, compute_skill_hash


class SkillLoadError(Exception):
    pass


def _parse_skill_md_text(text: str) -> tuple[dict, str]:
    if text.startswith("---"):
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.DOTALL)
        if match:
            frontmatter = yaml.safe_load(match.group(1)) or {}
            body = match.group(2).strip()
            return frontmatter, body
    return {}, text.strip()


def _read_skill_body_from_path(path: Path) -> str:
    return _parse_skill_md_text(path.read_text(encoding="utf-8"))[1]


def _skill_path(skill_name: str) -> Path:
    path = skills_root() / skill_name / "SKILL.md"
    if not path.is_file():
        raise SkillLoadError(f"Unknown skill: {skill_name}")
    return path


def _verify_content_hash(expected_hash: str, body: str, *, skill_name: str) -> None:
    if not expected_hash:
        return
    actual = compute_skill_hash(body)
    if actual != expected_hash:
        raise SkillLoadError(f"Skill '{skill_name}' hash mismatch — content rejected")


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
    registry: SkillRegistry | None = None,
) -> str:
    if skill_name not in allowed_skills:
        raise SkillLoadError(f"Skill '{skill_name}' not allowlisted for persona '{persona}'")

    reg = registry or SkillRegistry.load()
    body: str | None = None
    expected_hash = ""

    catalog_body = _load_from_catalog(skill_name, profile_id=profile_id)
    if catalog_body is not None:
        body = catalog_body
        entry = get_skill_catalog().get_skill(skill_name, profile_id=profile_id)
        if entry is not None:
            expected_hash = entry.content_hash
    else:
        try:
            manifest = reg.get(skill_name)
        except KeyError:
            manifest = None

        if manifest is not None and manifest.path:
            path = Path(manifest.path)
            if not path.is_file():
                raise SkillLoadError(f"Unknown skill: {skill_name}")
            body = _read_skill_body_from_path(path)
            expected_hash = manifest.content_hash
        else:
            path = _skill_path(skill_name)
            body = _read_skill_body_from_path(path)
            try:
                expected_hash = reg.get(skill_name).content_hash
            except KeyError:
                expected_hash = ""

    if body is None:
        raise SkillLoadError(f"Unknown skill: {skill_name}")
    _verify_content_hash(expected_hash, body, skill_name=skill_name)

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
