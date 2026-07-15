from __future__ import annotations

import json
from contextlib import contextmanager

import httpx
import pytest

from cys_core.domain.tools.models import ToolInvokeCommand
from cys_core.infrastructure.tools.adapters.siem import query_siem_readonly_search


def _patch_sync_http_client(monkeypatch: pytest.MonkeyPatch, mock_client: httpx.Client) -> None:
    def _fake_invoke_mcp_sync(**_kwargs: object) -> dict:
        response = mock_client.post(_kwargs.get("url", ""), json=_kwargs.get("payload"))
        return response.json()

    monkeypatch.setattr(
        "cys_core.integrations.mcp_http.invoke_mcp_sync",
        _fake_invoke_mcp_sync,
    )


@pytest.mark.unit
def test_query_siem_readonly_delegates_to_mcp(monkeypatch: pytest.MonkeyPatch) -> None:
    import cys_core.application.runtime_config as rc
    from bootstrap.settings import get_settings

    monkeypatch.setattr(rc, "_siem_mcp_enabled", True)
    monkeypatch.setattr(get_settings(), "siem_mcp_enabled", True)

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["params"]["name"] == "search_events"
        assert body["params"]["arguments"]["where"] == "powershell"
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {"content": [{"type": "text", "text": '{"events":[]}'}]},
            },
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    _patch_sync_http_client(monkeypatch, mock_client)

    result = query_siem_readonly_search(query="powershell", time_range="24h")
    assert result["adapter"] == "siem-mcp"
    assert result["source"] == "siem-mcp"


@pytest.mark.unit
def test_invoke_tool_routes_siem_mcp(monkeypatch: pytest.MonkeyPatch) -> None:
    import cys_core.application.runtime_config as rc
    from bootstrap.container import get_container

    monkeypatch.setattr(rc, "_siem_mcp_enabled", True)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "content": [{"type": "text", "text": json.dumps({"incidents": []})}]
                },
            },
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    _patch_sync_http_client(monkeypatch, mock_client)

    gateway = get_container().get_tool_execution_gateway()
    result = gateway.invoke(
        ToolInvokeCommand(
            tool_name="list_incidents",
            args={"limit": 5},
            persona="soc",
            sandbox_id="sandbox-siem-2",
            profile_id="cybersec-soc",
        )
    )
    assert result.success is True
