from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from cys_core.integrations.veil_mcp_client import call_veil_mcp_tool
from interfaces.gateways.tool.adapters.veil_mcp import call_veil_tool
from interfaces.gateways.tool.server import create_app


@pytest.mark.unit
def test_call_veil_mcp_tool_success(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["method"] == "tools/call"
        assert body["params"]["name"] == "playbook_search"
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps({"count": 1, "skills": [{"id": "forensics-1"}]}),
                        }
                    ]
                },
            },
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))

    class _ClientFactory:
        def __init__(self, timeout: float) -> None:
            self._client = mock_client

        def __enter__(self) -> httpx.Client:
            return self._client

        def __exit__(self, *args: object) -> None:
            self._client.close()

    monkeypatch.setattr("cys_core.integrations.veil_mcp_client.httpx.Client", _ClientFactory)
    result = call_veil_mcp_tool("playbook_search", {"query": "forensics", "limit": 2})
    assert result["success"] is True
    assert result["content"]["count"] == 1


@pytest.mark.unit
def test_call_veil_mcp_tool_disabled(monkeypatch):
    from bootstrap.settings import settings

    monkeypatch.setattr(settings, "veil_mcp_enabled", False)
    result = call_veil_tool("playbook_search", {"query": "x"})
    assert result["success"] is False
    assert "disabled" in result["error"]


@pytest.mark.unit
def test_gateway_invoke_playbook_search(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {"content": [{"type": "text", "text": '{"count":0,"skills":[]}'}]},
            },
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))

    class _ClientFactory:
        def __init__(self, timeout: float) -> None:
            self._client = mock_client

        def __enter__(self) -> httpx.Client:
            return self._client

        def __exit__(self, *args: object) -> None:
            self._client.close()

    monkeypatch.setattr("cys_core.integrations.veil_mcp_client.httpx.Client", _ClientFactory)

    client = TestClient(create_app())
    response = client.post(
        "/invoke",
        json={
            "tool_name": "playbook_search",
            "args": {"query": "forensics", "limit": 3},
            "persona": "soc",
            "sandbox_id": "sandbox-veil-1",
        },
    )
    body = response.json()
    assert body["success"] is True
    assert "BEGIN_RETRIEVED_CONTENT" in body["sanitized_payload"]
