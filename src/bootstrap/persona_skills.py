from __future__ import annotations

from pathlib import Path

import yaml

from cys_core.domain.catalog.models import AgentCatalogEntry
from cys_core.registry.product_context import default_agents_root


def load_persona_skills_map(root: Path | None = None) -> dict[str, list[str]]:
    path = (root or default_agents_root()) / "persona_skills.yaml"
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return {}
    result: dict[str, list[str]] = {}
    for persona, skills in data.items():
        if isinstance(skills, list):
            result[str(persona)] = [str(s) for s in skills if s]
    return result


def apply_persona_skills(entries: list[AgentCatalogEntry], root: Path | None = None) -> list[AgentCatalogEntry]:
    mapping = load_persona_skills_map(root)
    if not mapping:
        return entries
    updated: list[AgentCatalogEntry] = []
    for entry in entries:
        extra = mapping.get(entry.name)
        if not extra:
            updated.append(entry)
            continue
        merged = list(dict.fromkeys([*entry.skills, *extra]))
        updated.append(entry.model_copy(update={"skills": merged}))
    return updated
