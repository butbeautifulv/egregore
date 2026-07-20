from __future__ import annotations

from cys_core.application.ports.agents_root import AgentsRootPort
from cys_core.application.ports.skill_registry import SkillRegistryPort

_skill_registry: SkillRegistryPort | None = None
_agents_root: AgentsRootPort | None = None


def configure_skill_registry(port: SkillRegistryPort) -> None:
    global _skill_registry
    _skill_registry = port


def configure_skills_agents_root(port: AgentsRootPort) -> None:
    global _agents_root
    _agents_root = port


def list_skill_metadata(profile_id: str = "") -> list[dict[str, str]]:
    if _skill_registry is None:
        raise RuntimeError("Skill registry not configured — wire via bootstrap Container")
    return _skill_registry.list_metadata(profile_id)


def skills_root(agents_root: AgentsRootPort | None = None):
    root = agents_root or _agents_root
    if root is None:
        raise RuntimeError("Skills agents root not configured — wire via bootstrap Container")
    return root.agents_root() / "skills"
