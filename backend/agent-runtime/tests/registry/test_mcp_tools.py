from __future__ import annotations

import json

import pytest

from cys_core.registry.mcp_tools import (
    HITL_MARKER_KEY,
    McpToolRegistry,
    parse_hitl_marker,
    require_sandbox,
    use_approval_token,
)


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


@pytest.mark.unit
def test_parse_hitl_marker_roundtrips_and_rejects_lookalikes():
    marker = json.dumps({HITL_MARKER_KEY: True, "tool_name": "run_active_scan", "approval_token": "tok-1"})
    parsed = parse_hitl_marker(marker)
    assert parsed is not None
    assert parsed["approval_token"] == "tok-1"
    assert parse_hitl_marker(json.dumps({"error": "boom"})) is None
    assert parse_hitl_marker("not json at all") is None
    assert parse_hitl_marker(json.dumps({HITL_MARKER_KEY: False})) is None


@pytest.mark.unit
def test_run_closure_surfaces_hitl_marker_instead_of_generic_error(monkeypatch):
    """A gateway refusal (hitl_required=True) must not collapse into the generic
    {"error": ...} string — SecurityMiddleware needs the structured marker to tell a
    HITL pause apart from an ordinary tool failure. docs/MSP_BACKLOG.md §35/§58."""
    reg = McpToolRegistry(use_gateway=False)
    monkeypatch.setattr(
        reg,
        "invoke",
        lambda *a, **kw: {
            "success": False,
            "hitl_required": True,
            "risk_level": "high",
            "approval_token": "tok-xyz",
        },
    )
    tools = reg.resolve(["dedup_alerts"], "sandbox-1", persona="soc")
    content = tools[0].func()
    marker = parse_hitl_marker(content)
    assert marker is not None
    assert marker["risk_level"] == "high"
    assert marker["approval_token"] == "tok-xyz"


@pytest.mark.unit
def test_run_closure_threads_pending_approval_token_into_invoke(monkeypatch):
    reg = McpToolRegistry(use_gateway=False)
    seen = {}

    def fake_invoke(*_a, **kwargs):
        seen["approval_token"] = kwargs.get("approval_token")
        return {"success": True, "data": {}}

    monkeypatch.setattr(reg, "invoke", fake_invoke)
    tools = reg.resolve(["dedup_alerts"], "sandbox-1", persona="soc")
    with use_approval_token("tok-retry"):
        tools[0].func()
    assert seen["approval_token"] == "tok-retry"
    tools[0].func()
    assert seen["approval_token"] == ""
