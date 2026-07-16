from __future__ import annotations

from cys_core.application.ports.tool_registry import ToolRegistryPort
from cys_core.registry.tools import ToolRegistry, tool_registry


class ToolRegistryAdapter:
    def __init__(self, registry: ToolRegistry | None = None) -> None:
        self._registry = registry or tool_registry

    def get(self, name: str):
        return self._registry.get(name)

    def names(self, *, profile_id: str | None = None) -> list[str]:
        return self._registry.names(profile_id=profile_id)

    def resolve(self, names: list[str], profile_id: str = "cybersec-soc"):
        return self._registry.resolve(names, profile_id=profile_id)


def build_tool_registry_port(registry: ToolRegistry | None = None) -> ToolRegistryPort:
    return ToolRegistryAdapter(registry)
