from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from interfaces.gateways.tool.adapters.siem import query_siem_readonly_search
from interfaces.gateways.tool.handler import invoke_tool
from interfaces.gateways.tool.models import ToolInvokeRequest
from interfaces.gateways.tool.server import create_app


@pytest.mark.unit
def test_query_siem_readonly_search_mock():
    data = query_siem_readonly_search(query="powershell -enc", time_range="1h")
    assert data["readonly"] is True
    assert data["result_count"] >= 1
    assert "powershell -enc" in data["results"][0]["message"]


@pytest.mark.unit
def test_gateway_invoke_query_siem_readonly():
    client = TestClient(create_app())
    response = client.post(
        "/invoke",
        json={
            "tool_name": "query_siem_readonly",
            "args": {"query": "lateral movement", "time_range": "6h"},
            "persona": "soc",
            "sandbox_id": "sandbox-soc-1",
            "job_id": "soc-evt-1",
        },
    )
    body = response.json()
    assert body["success"] is True
    assert body["data"]["readonly"] is True
    assert body["data"]["query"] == "lateral movement"
    assert "RETRIEVED_TOOL_DATA" in body["sanitized_payload"]


@pytest.mark.unit
def test_handler_uses_adapter_not_registry_stub(monkeypatch):
    monkeypatch.setattr(
        "interfaces.gateways.tool.handler.invoke_adapter",
        lambda name, args: {"adapter": True, "query": args.get("query", "")},
    )

    response = invoke_tool(
        ToolInvokeRequest(
            tool_name="query_siem_readonly",
            args={"query": "beacon"},
            persona="soc",
            sandbox_id="sandbox-1",
        )
    )
    assert response.success is True
    assert response.data["adapter"] is True
