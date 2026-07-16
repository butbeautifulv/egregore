from __future__ import annotations

from cys_core.application.ports.skill_registry import SkillRegistryPort
from cys_core.registry.skill_registry import SkillRegistry


class SkillRegistryAdapter:
    def list_metadata(self, profile_id: str = "") -> list[dict[str, str]]:
        reg = SkillRegistry.load()
        items: list[dict[str, str]] = []
        for manifest in reg.all():
            skill_id = manifest.skill_id
            if profile_id == "gaia-bench" and skill_id.startswith("dfir"):
                continue
            items.append(
                {
                    "id": skill_id,
                    "name": manifest.name,
                    "description": manifest.description,
                }
            )
        return items


def build_skill_registry_port() -> SkillRegistryPort:
    return SkillRegistryAdapter()
