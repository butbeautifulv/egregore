from __future__ import annotations

from cys_core.application.ports.catalog import AgentCatalogPort
from cys_core.application.ports.persona_ranking import PersonaRankingPort
from cys_core.application.runtime_config import get_use_dynamic_catalog
from cys_core.infrastructure.policy.mode_policy_adapter import allow_tool_for_profile
from cys_core.domain.runs.models import InteractionMode
from cys_core.infrastructure.catalog.profile_policy import get_trust_floor
from cys_core.registry.agents import AgentRegistry
from cys_core.registry.skill_registry import SkillRegistry
from cys_core.registry.tools import list_tools

_catalog_provider: AgentCatalogPort | None = None
_ranking_provider: PersonaRankingPort | None = None


def set_catalog_provider(catalog: AgentCatalogPort | None) -> None:
    global _catalog_provider
    _catalog_provider = catalog


def set_persona_ranking_provider(port: PersonaRankingPort | None) -> None:
    global _ranking_provider
    _ranking_provider = port


def _default_catalog() -> AgentCatalogPort | None:
    if not get_use_dynamic_catalog():
        return None
    if _catalog_provider is not None:
        return _catalog_provider
    try:
        from bootstrap.container import get_container

        return get_container().get_agent_catalog()
    except Exception:
        try:
            from cys_core.infrastructure.catalog.catalog_registry import get_agent_catalog

            return get_agent_catalog()
        except Exception:
            return None


def _persona_trust_score(name: str, catalog: AgentCatalogPort | None) -> float:
    if catalog is not None:
        entry = catalog.get_agent(name)
        if entry is not None:
            return entry.quality.empirical_trust
    return 0.75


def search_personas(
    query: str,
    *,
    catalog: AgentCatalogPort | None = None,
    profile_id: str = "cybersec-soc",
    limit: int = 5,
) -> list[dict]:
    catalog = catalog or _default_catalog()
    if catalog is not None:
        q = query.lower()
        hits: list[str] = []
        for entry in catalog.list_agents(profile_id=profile_id, enabled_only=True):
            haystack = " ".join([entry.name, entry.description.lower(), " ".join(entry.capabilities)]).lower()
            if q in haystack:
                hits.append(entry.name)
        hits.sort(key=lambda name: _persona_trust_score(name, catalog), reverse=True)
        return [
            {
                "name": name,
                "description": catalog.get_agent(name).description if catalog.get_agent(name) else "",
                "capabilities": catalog.get_agent(name).capabilities if catalog.get_agent(name) else [],
                "empirical_trust": _persona_trust_score(name, catalog),
            }
            for name in hits[:limit]
        ]

    registry = AgentRegistry.load()
    names = registry.names()
    q = query.lower()
    hits = []
    for name in names:
        agent = registry.get(name)
        haystack = " ".join([name, agent.description.lower(), " ".join(agent.capabilities)]).lower()
        if q in haystack:
            hits.append(name)
    hits.sort(key=lambda name: _persona_trust_score(name, catalog), reverse=True)
    return [
        {
            "name": name,
            "description": registry.get(name).description,
            "capabilities": registry.get(name).capabilities,
            "empirical_trust": _persona_trust_score(name, catalog),
        }
        for name in hits[:limit]
    ]


def search_skills(query: str, *, profile_id: str = "cybersec-soc", limit: int = 5) -> list[dict]:
    if get_use_dynamic_catalog():
        try:
            from cys_core.infrastructure.catalog.registry_factory import get_skill_catalog

            q = query.lower()
            hits = [
                entry
                for entry in get_skill_catalog().list_skills(profile_id=profile_id, enabled_only=True)
                if q in entry.id or q in (entry.description or "").lower()
            ]
            return [{"id": entry.id, "description": entry.description} for entry in hits[:limit]]
        except Exception:
            pass
    reg = SkillRegistry.load()
    q = query.lower()
    hits = [sid for sid in reg.names() if q in sid or q in (reg.get(sid).description or "").lower()]
    return [{"id": sid, "description": reg.get(sid).description} for sid in hits[:limit]]


def search_tools(
    query: str,
    *,
    mode: InteractionMode | None = None,
    profile_id: str = "cybersec-soc",
    limit: int = 10,
) -> list[dict]:
    q = query.lower()
    names = list_tools(profile_id=profile_id)
    hits = [name for name in names if q in name]
    allowed = [name for name in hits if allow_tool_for_profile(mode, name, profile_id)]
    return [{"name": name} for name in allowed[:limit]]


def rank_personas_by_quality(
    personas: list[str], *, catalog: AgentCatalogPort | None = None, profile_id: str = "cybersec-soc"
) -> list[str]:
    if _ranking_provider is not None:
        return _ranking_provider.rank(personas, profile_id=profile_id)
    catalog = catalog or _default_catalog()
    floor = get_trust_floor(profile_id)
    scored = [(name, _persona_trust_score(name, catalog)) for name in personas]
    scored = [(name, score) for name, score in scored if score >= floor]
    scored.sort(key=lambda item: item[1], reverse=True)
    return [name for name, _ in scored]
