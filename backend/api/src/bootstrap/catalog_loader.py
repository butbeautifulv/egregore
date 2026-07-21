from __future__ import annotations

from bootstrap.product_loader import load_agent_definitions
from cys_core.domain.catalog.models import AgentCatalogEntry, ProfilePack
from cys_core.infrastructure.catalog.catalog_mapper import definition_to_entry, entry_to_definition

DEFAULT_PROFILE_ID = "cybersec-soc"

__all__ = [
    "DEFAULT_PROFILE_ID",
    "definition_to_entry",
    "entry_to_definition",
    "load_active_profile_pack",
    "load_profile_pack",
    "load_profile_pack_for",
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


def load_profile_pack_for(pack_id: str) -> tuple[ProfilePack, list[AgentCatalogEntry]]:
    """Load a ProfilePack + AgentCatalogEntry list scoped to a specific product pack.

    `pack_id == DEFAULT_PROFILE_ID` (cybersec-soc) delegates to `load_profile_pack()`
    unchanged: that pack's declared `personas` list is a stub pointer set (2 entries),
    not a complete persona catalog (17 personas actually exist on disk) — filtering by
    it would silently drop real SOC personas. Any other pack in `PRODUCT_PACKS` is
    filtered down to just the personas it declares.
    """
    from bootstrap.persona_skills import apply_persona_skills
    from bootstrap.product_packs import PRODUCT_PACKS, product_pack_to_profile_pack

    if pack_id == DEFAULT_PROFILE_ID:
        return load_profile_pack()

    pack = PRODUCT_PACKS.get(pack_id)
    if pack is None:
        raise KeyError(f"Unknown product pack: {pack_id}")

    allowed = {p.catalog_agent for p in pack.personas if p.enabled}
    agents = load_agent_definitions()
    filtered = {name: defn for name, defn in agents.items() if name in allowed}
    profile = product_pack_to_profile_pack(pack)
    entries = apply_persona_skills([definition_to_entry(defn) for defn in filtered.values()])
    return profile, entries


def load_active_profile_pack() -> tuple[ProfilePack, list[AgentCatalogEntry]]:
    """Zero-arg entrypoint for SeedCatalog: resolves the active pack from PROFILE_PACK_ID."""
    import os

    return load_profile_pack_for(os.environ.get("PROFILE_PACK_ID", DEFAULT_PROFILE_ID))
