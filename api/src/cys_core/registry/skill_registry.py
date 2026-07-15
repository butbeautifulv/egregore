from __future__ import annotations

import hashlib
import re
from functools import lru_cache
from pathlib import Path

import yaml

from cys_core.domain.skills.models import SkillManifest, SkillTrustTier
from cys_core.registry.product_context import default_agents_root


def _parse_skill_md(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.DOTALL)
        if match:
            frontmatter = yaml.safe_load(match.group(1)) or {}
            body = match.group(2).strip()
            return frontmatter, body
    return {}, text.strip()


def compute_skill_hash(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


class SkillRegistry:
    """Load builtin product skills from agents/skills/."""

    def __init__(self, skills: dict[str, SkillManifest]) -> None:
        self._skills = skills

    @classmethod
    def load(cls, root: Path | None = None, *, manifest_skill_ids: list[str] | None = None) -> SkillRegistry:
        agents_root = root or default_agents_root()
        skills_dir = agents_root / "skills"
        manifest_ids = manifest_skill_ids
        if manifest_ids is None:
            manifest_path = agents_root / "manifest.yaml"
            if manifest_path.exists():
                data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
                manifest_ids = list(data.get("skills", []))
            else:
                manifest_ids = []

        loaded: dict[str, SkillManifest] = {}
        for skill_id in manifest_ids:
            skill_dir = skills_dir / skill_id
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue
            frontmatter, body = _parse_skill_md(skill_md)
            name = str(frontmatter.get("name") or skill_id)
            loaded[name] = SkillManifest(
                skill_id=skill_id,
                name=name,
                description=str(frontmatter.get("description") or ""),
                version=str(frontmatter.get("version") or "1.0.0"),
                content_hash=compute_skill_hash(body),
                trust_tier=SkillTrustTier.BUILTIN,
                path=str(skill_md),
                author=str(frontmatter.get("author") or "cys-agi"),
            )
        return cls(loaded)

    def get(self, name: str) -> SkillManifest:
        if name not in self._skills:
            raise KeyError(f"Unknown skill: {name}")
        return self._skills[name]

    def names(self) -> list[str]:
        return list(self._skills.keys())

    def all(self) -> list[SkillManifest]:
        return list(self._skills.values())

    def metadata_block(self, names: list[str] | None = None) -> str:
        selected = [self._skills[n] for n in (names or self.names()) if n in self._skills]
        if not selected:
            return ""
        lines = ["AVAILABLE_SKILLS (metadata only — use load_skill to fetch body):"]
        for skill in selected:
            lines.append(f"- {skill.name}: {skill.description}")
        return "\n".join(lines)


@lru_cache
def get_skill_registry() -> SkillRegistry:
    return SkillRegistry.load()
