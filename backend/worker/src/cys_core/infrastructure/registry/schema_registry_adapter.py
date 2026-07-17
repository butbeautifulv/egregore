from __future__ import annotations

from cys_core.application.ports.schema_registry import SchemaRegistryPort
from cys_core.registry.schemas import SchemaRegistry, schema_registry


class SchemaRegistryAdapter:
    def __init__(self, registry: SchemaRegistry | None = None) -> None:
        self._registry = registry or schema_registry

    def get(self, name: str | None):
        return self._registry.get(name)


def build_schema_registry_port(registry: SchemaRegistry | None = None) -> SchemaRegistryPort:
    return SchemaRegistryAdapter(registry)
