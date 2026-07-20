from __future__ import annotations

import pytest

from cys_core.registry.tools import tool_registry


@pytest.mark.unit
def test_discovery_tools_registered():
    names = tool_registry.names()
    assert "search_personas" in names
    assert "search_skills" in names
    assert "search_tools" in names


@pytest.mark.unit
def test_search_personas_tool_returns_json():
    tool = tool_registry.get("search_personas")
    result = tool.invoke({"query": "soc"})
    assert "soc" in result.lower()
