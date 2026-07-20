from __future__ import annotations

import pytest
import yaml

from cys_core.integrations.siem_mcp_client import FALLBACK_SIEM_TOOL_NAMES
from cys_core.registry.product_context import default_agents_root
from cys_core.registry.tools import tool_registry


@pytest.mark.unit
def test_soc_agent_includes_siem_mcp_tools():
    # Computed inside the test, not at module level: default_agents_root()
    # only resolves correctly once the autouse conftest fixture has patched
    # settings.agents_root, which happens per-test, after collection.
    soc_yaml = default_agents_root() / "personas" / "soc" / "agent.yaml"
    data = yaml.safe_load(soc_yaml.read_text(encoding="utf-8"))
    tools = data["tools"]
    skills = data["skills"]
    assert "investigate_incident" in tools
    assert "list_incidents" in tools
    assert "search_events" in tools
    assert "get_event_by_uuid" in tools
    assert "siem-investigation" in skills
    assert "rag_query" in tools
    assert "playbook_search" in tools


@pytest.mark.unit
def test_siem_tools_registered_in_registry():
    names = set(tool_registry.names())
    for tool_name in FALLBACK_SIEM_TOOL_NAMES:
        assert tool_name in names


@pytest.mark.unit
def test_siem_investigation_skill_exists():
    skill_path = default_agents_root() / "skills" / "siem-investigation" / "SKILL.md"
    assert skill_path.is_file()
    text = skill_path.read_text(encoding="utf-8")
    assert "investigate_incident" in text
    assert "list_incidents" in text
