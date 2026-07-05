from __future__ import annotations

from bootstrap.product_loader import load_agent_definitions
from cys_core.domain.catalog.models import AgentCatalogEntry, ProfilePack
from cys_core.infrastructure.catalog.catalog_mapper import definition_to_entry, entry_to_definition

DEFAULT_PROFILE_ID = "cybersec-soc"

__all__ = [
    "DEFAULT_PROFILE_ID",
    "definition_to_entry",
    "entry_to_definition",
    "load_profile_pack",
]


def load_profile_pack() -> tuple[ProfilePack, list[AgentCatalogEntry]]:
    from bootstrap.persona_skills import apply_persona_skills
    from bootstrap.policy_defaults import default_profile_pack

    agents = load_agent_definitions()
    workers = [a for a in agents.values() if a.role in ("worker", "specialist")]
    profile = default_profile_pack(
        id=DEFAULT_PROFILE_ID,
        default_personas=[a.name for a in workers],
    )
    entries = apply_persona_skills([definition_to_entry(defn) for defn in agents.values()])
    return profile, entries
