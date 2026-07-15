from __future__ import annotations

import json
from contextlib import contextmanager

import httpx
import pytest
from fastapi.testclient import TestClient

from cys_core.integrations.siem_mcp_client import call_siem_mcp_tool
from interfaces.gateways.tool.adapters.siem_mcp import call_siem_tool
from interfaces.gateways.tool.server import create_app


def _patch_sync_http_client(monkeypatch: pytest.MonkeyPatch, mock_client: httpx.Client) -> None:
    @contextmanager
    def _fake_sync_http_client(**_kwargs: object):
        yield mock_client

    monkeypatch.setattr(
        "cys_core.integrations.siem_mcp_client.sync_http_client",
        _fake_sync_http_client,
    )


@pytest.mark.unit
def test_call_siem_mcp_tool_success(monkeypatch: pytest.MonkeyPatch) -> None:
    import cys_core.application.runtime_config as rc

    monkeypatch.setattr(rc, "_siem_mcp_enabled", True)

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["method"] == "tools/call"
        assert body["params"]["name"] == "investigate_incident"
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps({"incident_id": "INC-42", "summary": {"key": "INC-42"}}),
                        }
                    ]
                },
            },
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    _patch_sync_http_client(monkeypatch, mock_client)
    result = call_siem_mcp_tool("investigate_incident", {"incident_id": "INC-42"})
    assert result["success"] is True
    assert result["source"] == "siem-mcp"
    assert result["content"]["incident_id"] == "INC-42"


@pytest.mark.unit
def test_call_siem_mcp_tool_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    import cys_core.application.runtime_config as rc

    monkeypatch.setattr(rc, "_siem_mcp_enabled", False)
    result = call_siem_tool("investigate_incident", {"incident_id": "INC-42"})
    assert result["success"] is False
    assert "disabled" in result["error"]


@pytest.mark.unit
def test_gateway_invoke_investigate_incident(monkeypatch: pytest.MonkeyPatch) -> None:
    import cys_core.application.runtime_config as rc

    monkeypatch.setattr(rc, "_siem_mcp_enabled", True)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "content": [
                        {"type": "text", "text": json.dumps({"incident_id": "INC-42", "events": []})}
                    ]
                },
            },
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    _patch_sync_http_client(monkeypatch, mock_client)

    client = TestClient(create_app())
    response = client.post(
        "/invoke",
        json={
            "tool_name": "investigate_incident",
            "args": {"incident_id": "INC-42"},
            "persona": "soc",
            "sandbox_id": "sandbox-siem-1",
        },
    )
    body = response.json()
    assert body["success"] is True
    assert "BEGIN_RETRIEVED_CONTENT" in body["sanitized_payload"]
