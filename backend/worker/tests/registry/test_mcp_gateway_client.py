from __future__ import annotations

import json

import httpx
import pytest

from cys_core.registry.mcp_tools import McpToolRegistry


@pytest.mark.unit
def test_mcp_gateway_http_invoke():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "success": True,
                "tool_name": body["tool_name"],
                "data": {"deduplicated_count": 1},
                "sanitized_payload": "RETRIEVED_TOOL_DATA\nBEGIN_RETRIEVED_CONTENT\nok\nEND_RETRIEVED_CONTENT",
            },
        )

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    reg = McpToolRegistry(gateway_url="http://gateway", use_gateway=True, client=client)
    result = reg.invoke("dedup_alerts", "sandbox-1", {"alerts_text": "a"}, persona="soc")
    assert result["success"] is True
    assert "RETRIEVED_TOOL_DATA" in result["sanitized_payload"]


@pytest.mark.unit
async def test_mcp_gateway_ainvoke_uses_async_client_not_a_thread(monkeypatch):
    """ainvoke should call the gateway directly via an AsyncClient, not thread-wrap
    the sync invoke() — assert the sync path is never touched during an async call."""

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "success": True,
                "tool_name": body["tool_name"],
                "data": {"deduplicated_count": 1},
                "sanitized_payload": "ok",
            },
        )

    transport = httpx.MockTransport(handler)
    async_client = httpx.AsyncClient(transport=transport)
    reg = McpToolRegistry(gateway_url="http://gateway", use_gateway=True, async_client=async_client)

    def _fail_if_called(*_args, **_kwargs):
        raise AssertionError("sync invoke() must not be called from ainvoke()")

    monkeypatch.setattr(reg, "invoke", _fail_if_called)

    result = await reg.ainvoke("dedup_alerts", "sandbox-1", {"alerts_text": "a"}, persona="soc")
    assert result["success"] is True
    await async_client.aclose()


@pytest.mark.unit
async def test_mcp_gateway_ainvoke_falls_back_to_local_on_gateway_error():
    from bootstrap.container import get_container

    get_container()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    transport = httpx.MockTransport(handler)
    async_client = httpx.AsyncClient(transport=transport)
    reg = McpToolRegistry(gateway_url="http://gateway", use_gateway=True, async_client=async_client)

    result = await reg.ainvoke("dedup_alerts", "sandbox-1", {"alerts_text": "alert"}, persona="soc")
    assert result["success"] is True
    assert "deduplicated_count" in result["data"]
    await async_client.aclose()
