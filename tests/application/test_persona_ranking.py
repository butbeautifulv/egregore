from __future__ import annotations

import pytest

from cys_core.infrastructure.catalog.persona_ranking import PersonaRankingService
from tests.application.port_fakes import fake_agent_catalog, fake_policy_port


@pytest.mark.unit
def test_persona_ranking_filters_below_trust_floor():
    catalog = fake_agent_catalog(enabled=["soc", "network"])
    catalog.get_agent = lambda name: type(
        "Entry",
        (),
        {
            "name": name,
            "enabled": True,
            "quality": type("Q", (), {"empirical_trust": 0.3 if name == "network" else 0.9})(),
        },
    )()
    policy = fake_policy_port(trust_floor=0.5)
    service = PersonaRankingService(catalog=catalog, policy_port=policy)
    ranked = service.rank(["soc", "network"], profile_id="cybersec-soc")
    assert ranked == ["soc"]


@pytest.mark.unit
def test_persona_ranking_orders_by_trust_desc():
    catalog = fake_agent_catalog(enabled=["soc", "network"])

    def get_agent(name: str):
        trust = 0.9 if name == "network" else 0.6
        return type("Entry", (), {"quality": type("Q", (), {"empirical_trust": trust})()})()

    catalog.get_agent = get_agent
    policy = fake_policy_port(trust_floor=0.0)
    service = PersonaRankingService(catalog=catalog, policy_port=policy)
    ranked = service.rank(["soc", "network"], profile_id="cybersec-soc")
    assert ranked == ["network", "soc"]
