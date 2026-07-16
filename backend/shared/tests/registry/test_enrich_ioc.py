from __future__ import annotations

import json
from contextlib import contextmanager

import httpx
import pytest

from cys_core.registry.tools import enrich_ioc


def _patch_sync_http_client(monkeypatch: pytest.MonkeyPatch, mock_client: httpx.Client) -> None:
    @contextmanager
    def _fake_sync_http_client(**_kwargs: object):
        yield mock_client

    monkeypatch.setattr(
        "cys_core.integrations.veil_mcp_client.sync_http_client",
        _fake_sync_http_client,
    )


@pytest.mark.unit
def test_enrich_ioc_returns_veil_content(monkeypatch: pytest.MonkeyPatch) -> None:
    import cys_core.application.runtime_config as rc

    monkeypatch.setattr(rc, "_veil_mcp_enabled", True)

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["params"]["name"] == "ti_search_in_category"
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "content": [{"type": "text", "text": json.dumps({"hits": [{"id": "ioc-1"}]})}]
                },
            },
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    _patch_sync_http_client(monkeypatch, mock_client)

    result = json.loads(enrich_ioc.invoke({"ioc": "1.2.3.4"}))
    assert result["source"] == "veil-mcp"
    assert result["enrichment"]["hits"][0]["id"] == "ioc-1"


@pytest.mark.unit
def test_enrich_ioc_stub_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    import cys_core.application.runtime_config as rc

    monkeypatch.setattr(rc, "_veil_mcp_enabled", False)
    result = json.loads(enrich_ioc.invoke({"ioc": "evil.com"}))
    assert result["source"] == "stub"
