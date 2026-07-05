from __future__ import annotations

from cys_core.application.ports.agent_registry import AgentRegistryPort
from cys_core.registry.agents import AgentRegistry, get_agent_registry


class AgentRegistryAdapter:
    def __init__(self, registry: AgentRegistry | None = None) -> None:
        self._registry = registry or get_agent_registry()

    def get(self, name: str):
        return self._registry.get(name)

    def by_workers(self):
        return self._registry.by_workers()

    def names(self) -> list[str]:
        return self._registry.names()


def build_agent_registry_port(registry: AgentRegistry | None = None) -> AgentRegistryPort:
    return AgentRegistryAdapter(registry)
