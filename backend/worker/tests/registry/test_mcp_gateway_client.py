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
