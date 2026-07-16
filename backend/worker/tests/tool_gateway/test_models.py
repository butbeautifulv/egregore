from __future__ import annotations

import pytest

from interfaces.gateways.tool.models import ToolInvokeRequest, ToolInvokeResponse


@pytest.mark.unit
def test_tool_invoke_request_validation():
    req = ToolInvokeRequest(
        tool_name="dedup_alerts",
        args={"alerts_text": "x"},
        persona="soc",
        sandbox_id="sandbox-1",
    )
    assert req.tool_name == "dedup_alerts"
    assert req.sandbox_id == "sandbox-1"


@pytest.mark.unit
def test_tool_invoke_response_defaults():
    resp = ToolInvokeResponse(success=True, tool_name="dedup_alerts")
    assert resp.data == {}
    assert resp.error == ""
