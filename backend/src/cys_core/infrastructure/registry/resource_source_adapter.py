from __future__ import annotations

from cys_core.application.ports.agent_registry import AgentRegistryPort
from cys_core.application.ports.catalog import AgentCatalogPort
from cys_core.application.ports.resource_source import ResourceSourcePort
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID


class ResourceSourceAdapter:
    def __init__(
        self,
        agent_registry: AgentRegistryPort,
        *,
        agent_catalog: AgentCatalogPort | None = None,
    ) -> None:
        self._agent_registry = agent_registry
        self._agent_catalog = agent_catalog

    def list_worker_personas(self, profile_id: str | None = None) -> list[str]:
        pid = profile_id or DEFAULT_PROFILE_ID
        if self._agent_catalog is not None:
            entries = self._agent_catalog.list_agents(profile_id=pid, enabled_only=True)
            names = [entry.name for entry in entries if entry.role in ("worker", "specialist")]
            if names:
                return names
        return [agent.name for agent in self._agent_registry.by_workers()]


def build_resource_source_port(
    agent_registry: AgentRegistryPort,
    *,
    agent_catalog: AgentCatalogPort | None = None,
) -> ResourceSourcePort:
    return ResourceSourceAdapter(agent_registry, agent_catalog=agent_catalog)
