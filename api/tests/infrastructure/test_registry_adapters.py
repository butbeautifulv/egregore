from __future__ import annotations

import pytest

from bootstrap.agent_definitions_loader import get_default_agent_definitions_loader
from cys_core.infrastructure.registry.agent_registry_adapter import AgentRegistryAdapter
from cys_core.infrastructure.registry.schema_registry_adapter import SchemaRegistryAdapter
from cys_core.infrastructure.registry.tool_registry_adapter import ToolRegistryAdapter
from cys_core.registry.agents import AgentRegistry, configure_agent_definitions_loader
from cys_core.registry.schemas import schema_registry
from cys_core.registry.tools import tool_registry


@pytest.mark.unit
def test_agent_registry_adapter_delegates_get():
    configure_agent_definitions_loader(get_default_agent_definitions_loader())
    registry = AgentRegistry.load()
    adapter = AgentRegistryAdapter(registry)
    first = registry.names()[0]
    assert adapter.get(first) is registry.get(first)


@pytest.mark.unit
def test_schema_registry_adapter_delegates_get():
    adapter = SchemaRegistryAdapter(schema_registry)
    assert adapter.get("SocFinding") is schema_registry.get("SocFinding")


@pytest.mark.unit
def test_tool_registry_adapter_delegates_names():
    adapter = ToolRegistryAdapter(tool_registry)
    assert adapter.names() == tool_registry.names()
