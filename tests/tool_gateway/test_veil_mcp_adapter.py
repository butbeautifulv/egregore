from __future__ import annotations

import json
from contextlib import contextmanager

import httpx
import pytest
from fastapi.testclient import TestClient

from cys_core.integrations.veil_mcp_client import call_veil_mcp_tool
from interfaces.gateways.tool.adapters.veil_mcp import call_veil_tool
from interfaces.gateways.tool.server import create_app


def _patch_sync_http_client(monkeypatch: pytest.MonkeyPatch, mock_client: httpx.Client) -> None:
    @contextmanager
    def _fake_sync_http_client(**_kwargs: object):
        yield mock_client

    monkeypatch.setattr(
        "cys_core.integrations.veil_mcp_client.sync_http_client",
        _fake_sync_http_client,
    )


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
    _patch_sync_http_client(monkeypatch, mock_client)
    result = call_veil_mcp_tool("playbook_search", {"query": "forensics", "limit": 2})
    assert result["success"] is True
    assert result["content"]["count"] == 1


@pytest.mark.unit
def test_call_veil_mcp_tool_disabled(monkeypatch):
    import cys_core.application.runtime_config as rc

    monkeypatch.setattr(rc, "_veil_mcp_enabled", False)
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
    _patch_sync_http_client(monkeypatch, mock_client)

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
