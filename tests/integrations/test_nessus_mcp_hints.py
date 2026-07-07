from __future__ import annotations

import json

import httpx
import pytest

from cys_core.integrations import nessus_mcp_client as nmc


@pytest.mark.unit
def test_nessus_allowed_tools_default() -> None:
    tools = nmc.get_nessus_allowed_tools()
    assert "sync_scan_inventory" in tools
    assert "create_scan" in tools
    assert "launch_scan" in tools


@pytest.mark.unit
def test_call_nessus_mcp_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(nmc, "nessus_mcp_enabled", lambda: False)
    result = nmc.call_nessus_mcp_tool("list_scans")
    assert result["success"] is False
    assert "disabled" in result["error"].lower()


@pytest.mark.unit
def test_call_nessus_mcp_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(nmc, "nessus_mcp_enabled", lambda: True)

    class _Resp:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "result": {
                    "content": [
                        {"type": "text", "text": json.dumps({"scans": [{"id": 1}]})},
                    ]
                }
            }

    class _Client:
        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def post(self, url: str, json: dict) -> _Resp:
            return _Resp()

    monkeypatch.setattr(nmc, "sync_http_client", lambda **kwargs: _Client())
    monkeypatch.setattr(nmc, "get_nessus_mcp_url", lambda: "http://localhost:8095/mcp")
    monkeypatch.setattr(nmc, "get_nessus_mcp_timeout", lambda: 30.0)

    result = nmc.call_nessus_mcp_tool("list_scans")
    assert result["success"] is True
    assert result["source"] == "nessus-mcp"
