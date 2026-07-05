from __future__ import annotations

import pytest

from cys_core.registry.mcp_tools import McpToolRegistry, require_sandbox


@pytest.mark.unit
def test_require_sandbox_denies_host():
    with pytest.raises(PermissionError):
        require_sandbox("host")
    with pytest.raises(PermissionError):
        require_sandbox("")


@pytest.mark.unit
def test_mcp_tool_invoke_in_sandbox():
    from bootstrap.container import get_container

    get_container()
    reg = McpToolRegistry(use_gateway=False)
    result = reg.invoke("dedup_alerts", "sandbox-1", {"alerts_text": "alert"})
    assert result["success"] is True
    assert "deduplicated_count" in result["data"]


@pytest.mark.unit
def test_mcp_tool_resolve_returns_structured_tools():
    reg = McpToolRegistry(use_gateway=False)
    tools = reg.resolve(["dedup_alerts"], "sandbox-1", persona="soc")
    assert len(tools) == 1
    assert tools[0].name == "dedup_alerts"
