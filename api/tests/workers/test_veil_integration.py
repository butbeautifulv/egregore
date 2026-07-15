from __future__ import annotations

import json
from contextlib import contextmanager

import httpx
import pytest

from cys_core.domain.tools.models import ToolInvokeCommand


def _patch_sync_http_client(monkeypatch: pytest.MonkeyPatch, mock_client: httpx.Client) -> None:
    @contextmanager
    def _fake_sync_http_client(**_kwargs: object):
        yield mock_client

    monkeypatch.setattr(
        "cys_core.integrations.veil_mcp_client.sync_http_client",
        _fake_sync_http_client,
    )


@pytest.mark.unit
def test_invoke_tool_routes_playbook_search(monkeypatch: pytest.MonkeyPatch) -> None:
    import cys_core.application.runtime_config as rc
    from bootstrap.container import get_container

    monkeypatch.setattr(rc, "_veil_mcp_enabled", True)

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["params"]["name"] == "playbook_search"
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "content": [{"type": "text", "text": json.dumps({"count": 1, "skills": []})}]
                },
            },
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    _patch_sync_http_client(monkeypatch, mock_client)

    gateway = get_container().get_tool_execution_gateway()
    result = gateway.invoke(
        ToolInvokeCommand(
            tool_name="playbook_search",
            args={"query": "forensics", "limit": 3},
            persona="intel",
            sandbox_id="sandbox-veil-2",
            profile_id="cybersec-soc",
        )
    )
    assert result.success is True


@pytest.mark.unit
def test_invoke_tool_routes_ti_search(monkeypatch: pytest.MonkeyPatch) -> None:
    import cys_core.application.runtime_config as rc
    from bootstrap.container import get_container

    monkeypatch.setattr(rc, "_veil_mcp_enabled", True)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {"content": [{"type": "text", "text": '{"nodes":[]}'}]},
            },
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    _patch_sync_http_client(monkeypatch, mock_client)

    gateway = get_container().get_tool_execution_gateway()
    result = gateway.invoke(
        ToolInvokeCommand(
            tool_name="ti_search_in_category",
            args={"query": "CVE-2024", "category": "vuln"},
            persona="intel",
            sandbox_id="sandbox-veil-3",
            profile_id="cybersec-soc",
        )
    )
    assert result.success is True
