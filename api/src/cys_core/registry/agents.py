from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from cys_core.application.ports.agent_definitions import AgentDefinitionsLoaderPort
from cys_core.application.runtime_config import get_use_dynamic_catalog
from cys_core.domain.agents.models import AgentDefinition

_loader: AgentDefinitionsLoaderPort | None = None


def configure_agent_definitions_loader(loader: AgentDefinitionsLoaderPort) -> None:
    global _loader
    _loader = loader


class AgentRegistry:
    def __init__(self, agents: dict[str, AgentDefinition]) -> None:
        self._agents = agents

    @classmethod
    def load(
        cls,
        root: Path | None = None,
        loader: AgentDefinitionsLoaderPort | None = None,
    ) -> AgentRegistry:
        if root is not None:
            definitions_loader = loader
            if definitions_loader is None:
                from bootstrap.agent_definitions_loader import get_default_agent_definitions_loader

                definitions_loader = get_default_agent_definitions_loader()
            return cls(definitions_loader.load(root))
        if get_use_dynamic_catalog():
            from cys_core.infrastructure.catalog.catalog_registry import load_catalog_registry

            return load_catalog_registry(root)
        definitions_loader = loader or _loader
        if definitions_loader is None:
            raise RuntimeError("Agent definitions loader not configured")
        return cls(definitions_loader.load(root))

    def reload(self) -> None:
        """Reload agents from catalog + filesystem."""
        from cys_core.infrastructure.catalog.catalog_registry import reload_agent_registry

        refreshed = reload_agent_registry()
        self._agents = refreshed._agents

    def get(self, name: str) -> AgentDefinition:
        if name not in self._agents:
            raise KeyError(f"Unknown agent: {name}")
        return self._agents[name]

    def all(self) -> list[AgentDefinition]:
        return list(self._agents.values())

    def names(self) -> list[str]:
        return list(self._agents.keys())

    def by_role(self, role: str) -> list[AgentDefinition]:
        if role == "specialist":
            return self.by_workers()
        if role == "critic":
            return [a for a in self._agents.values() if a.name == "critic"]
        if role == "coordinator":
            return [a for a in self._agents.values() if a.name == "coordinator"]
        return [a for a in self._agents.values() if a.role == role]

    def by_workers(self) -> list[AgentDefinition]:
        return [a for a in self._agents.values() if a.role in ("worker", "specialist")]

    def by_control(self) -> list[AgentDefinition]:
        return [a for a in self._agents.values() if a.role in ("control", "critic", "coordinator")]


@lru_cache
def get_agent_registry() -> AgentRegistry:
    return AgentRegistry.load()
