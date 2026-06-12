from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from bootstrap.product_loader import load_agent_definitions
from cys_core.domain.agents.models import AgentDefinition


class AgentRegistry:
    def __init__(self, agents: dict[str, AgentDefinition]) -> None:
        self._agents = agents

    @classmethod
    def load(cls, root: Path | None = None) -> AgentRegistry:
        return cls(load_agent_definitions(root))

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
