from __future__ import annotations

from cys_core.application.ports.agent_registry import AgentRegistryPort
from cys_core.application.ports.resource_source import ResourceSourcePort


class ResourceSourceAdapter:
    def __init__(self, agent_registry: AgentRegistryPort) -> None:
        self._agent_registry = agent_registry

    def list_worker_personas(self, profile_id: str | None = None) -> list[str]:
        del profile_id
        return [agent.name for agent in self._agent_registry.by_workers()]


def build_resource_source_port(agent_registry: AgentRegistryPort) -> ResourceSourcePort:
    return ResourceSourceAdapter(agent_registry)
