from __future__ import annotations

from cys_core.application.ports.catalog import AgentCatalogPort
from cys_core.application.ports.persona_ranking import PersonaRankingPort
from cys_core.application.ports.profile_policy import ProfilePolicyPort


def _persona_trust_score(name: str, catalog: AgentCatalogPort | None) -> float:
    if catalog is not None:
        entry = catalog.get_agent(name)
        if entry is not None:
            return entry.quality.empirical_trust
    return 0.75


class PersonaRankingService:
    def __init__(
        self,
        *,
        catalog: AgentCatalogPort,
        policy_port: ProfilePolicyPort,
    ) -> None:
        self._catalog = catalog
        self._policy_port = policy_port

    def rank(self, personas: list[str], *, profile_id: str = "cybersec-soc") -> list[str]:
        floor = self._policy_port.get_trust_floor(profile_id)
        scored = [(name, _persona_trust_score(name, self._catalog)) for name in personas]
        scored = [(name, score) for name, score in scored if score >= floor]
        scored.sort(key=lambda item: item[1], reverse=True)
        return [name for name, _ in scored]


def build_persona_ranking_port(
    *,
    catalog: AgentCatalogPort,
    policy_port: ProfilePolicyPort,
) -> PersonaRankingPort:
    return PersonaRankingService(catalog=catalog, policy_port=policy_port)
