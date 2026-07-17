from __future__ import annotations

import pytest

from cys_core.domain.agents.models import AgentDefinition
from cys_core.infrastructure.registry.agent_registry_adapter import AgentRegistryAdapter, build_agent_registry_port
from cys_core.registry.agents import AgentRegistry


def _worker(name: str) -> AgentDefinition:
    return AgentDefinition(
        name=name,
        role="worker",
        description="",
        system_prompt="test",
        tools=[],
        skills=[],
    )


@pytest.mark.unit
def test_agent_registry_adapter_follows_reload(monkeypatch: pytest.MonkeyPatch) -> None:
    empty = AgentRegistry({})
    filled = AgentRegistry({"consultant": _worker("consultant")})

    calls = {"n": 0}

    def fake_get() -> AgentRegistry:
        calls["n"] += 1
        return empty if calls["n"] == 1 else filled

    monkeypatch.setattr(
        "cys_core.infrastructure.registry.agent_registry_adapter.get_agent_registry",
        fake_get,
    )

    adapter = AgentRegistryAdapter()
    assert adapter.names() == []
    assert adapter.names() == ["consultant"]
    assert [agent.name for agent in adapter.by_workers()] == ["consultant"]


@pytest.mark.unit
def test_build_agent_registry_port_can_pin_registry() -> None:
    registry = AgentRegistry({"soc": _worker("soc")})
    port = build_agent_registry_port(registry)
    assert port.names() == ["soc"]
