from __future__ import annotations

import json
from contextlib import contextmanager

import httpx
import pytest

from cys_core.integrations.veneno_mcp_client import call_veneno_mcp_tool
from interfaces.gateways.tool.adapters.veneno_mcp import call_veneno_tool


def _patch_sync_http_client(monkeypatch: pytest.MonkeyPatch, mock_client: httpx.Client) -> None:
    @contextmanager
    def _fake_sync_http_client(**_kwargs: object):
        yield mock_client

    monkeypatch.setattr(
        "cys_core.integrations.veneno_mcp_client.sync_http_client",
        _fake_sync_http_client,
    )


@pytest.mark.unit
def test_call_veneno_mcp_disabled(monkeypatch):
    import cys_core.application.runtime_config as rc

    monkeypatch.setattr(rc, "_veneno_mcp_enabled", False)
    result = call_veneno_mcp_tool("run_active_scan", {"target": "10.0.0.1"})
    assert result["success"] is False
    assert "disabled" in result["error"]


@pytest.mark.unit
def test_call_veneno_mcp_success(monkeypatch):
    import cys_core.application.runtime_config as rc

    monkeypatch.setattr(rc, "_veneno_mcp_enabled", True)
    monkeypatch.setattr(rc, "_veneno_mcp_url", "http://veneno-mcp.test/mcp")

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["params"]["name"] == "run_active_scan"
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {"content": [{"type": "text", "text": json.dumps({"status": "queued"})}]},
            },
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    _patch_sync_http_client(monkeypatch, mock_client)
    result = call_veneno_tool("run_active_scan", {"target": "10.0.0.1"})
    assert result["success"] is True
