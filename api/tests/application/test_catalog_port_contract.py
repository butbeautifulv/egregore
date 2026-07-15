from __future__ import annotations

import pytest

from cys_core.domain.catalog.models import AgentCatalogEntry, ProfilePack, ProfilePolicyPayload
from cys_core.infrastructure.catalog.memory import InMemoryAgentCatalog


@pytest.mark.unit
def test_agent_catalog_port_contract():
    catalog = InMemoryAgentCatalog()
    profile = ProfilePack(id="test-profile", name="Test")
    entry = AgentCatalogEntry(name="worker-a", profile_id="test-profile", tools=["web_search"])
    catalog.seed([entry], profile)

    agents = catalog.list_agents(profile_id="test-profile")
    assert len(agents) == 1
    assert agents[0].name == "worker-a"

    fetched = catalog.get_agent("worker-a")
    assert fetched is not None
    assert fetched.tools == ["web_search"]

    updated = catalog.upsert_agent(entry.model_copy(update={"description": "updated"}))
    assert updated.version == 2
    assert updated.description == "updated"

    version = catalog.get_version("test-profile")
    assert version.agent_count == 1
    assert version.profile_id == "test-profile"

    profiles = catalog.list_profiles()
    assert any(pack.id == "test-profile" for pack in profiles)

    assert catalog.delete_agent("worker-a", profile_id="test-profile") is True
    assert catalog.get_agent("worker-a") is not None
    assert catalog.get_agent("worker-a").enabled is False
