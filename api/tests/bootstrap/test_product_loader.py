from __future__ import annotations

import pytest

from bootstrap.product_loader import load_agent_definitions


@pytest.mark.unit
def test_load_agent_definitions_returns_named_agents():
    agents = load_agent_definitions()
    assert "soc" in agents
    assert agents["soc"].role == "worker"
    assert agents["soc"].system_prompt_digest
