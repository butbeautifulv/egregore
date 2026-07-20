from __future__ import annotations

import pytest

from cys_core.application.spawn_broker import SubagentSpawnBroker
from cys_core.domain.catalog.models import AgentCatalogEntry, PersonaQuality, ProfilePack, ProfilePolicyPayload
from cys_core.domain.runs.models import InteractionMode, RunContext
from cys_core.domain.runs.spawn import SpawnWorkerPayload
from cys_core.infrastructure.catalog.memory import InMemoryAgentCatalog
from tests.conftest import FakePolicyPort as _FakePolicyPort


@pytest.mark.unit
def test_spawn_broker_uses_injected_policy_port():
    catalog = InMemoryAgentCatalog()
    policy = ProfilePolicyPayload(trust_floor=0.9, max_spawn_depth=2)
    catalog.upsert_profile(ProfilePack(id="cybersec-soc", name="SOC", policy=policy))
    catalog.upsert_agent(
        AgentCatalogEntry(
            name="worker",
            profile_id="cybersec-soc",
            quality=PersonaQuality(empirical_trust=0.5),
        )
    )

    broker = SubagentSpawnBroker(catalog, policy_port=_FakePolicyPort(policy))
    parent = RunContext.from_session_id("s1", mode=InteractionMode.AGENT)
    payload = SpawnWorkerPayload(parent_context=parent, persona="worker", sub_goal="task")
    assert broker.validate(payload, mode=InteractionMode.AGENT) == "persona_quality_below_floor"
