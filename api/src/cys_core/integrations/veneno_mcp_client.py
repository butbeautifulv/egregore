from __future__ import annotations

import json
from typing import Any

import httpx

from cys_core.application.runtime_config import (
    get_veneno_mcp_timeout,
    get_veneno_mcp_url,
    veneno_mcp_enabled as _veneno_mcp_enabled,
)
from cys_core.infrastructure.http_client import sync_http_client
from cys_core.observability.tracing import inject_correlation_headers

# HITL-gated execution tools (veneno-mcp when enabled).
VENENO_MCP_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "run_active_scan",
        "execute_command",
        "engage_run_tool",
    }
)


class VenenoMcpError(Exception):
    """Veneno MCP request failed."""


def veneno_mcp_enabled() -> bool:
    return _veneno_mcp_enabled()


def call_veneno_mcp_tool(tool_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """Invoke one Veneno MCP tool via streamable HTTP (POST /mcp, tools/call)."""
    if not veneno_mcp_enabled():
        return {"success": False, "error": "Veneno MCP disabled (VENENO_MCP_ENABLED=false)", "source": "veneno-mcp"}
    if tool_name not in VENENO_MCP_TOOL_NAMES:
        return {"success": False, "error": f"Veneno tool not allowlisted: {tool_name}", "source": "veneno-mcp"}

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments or {}},
    }
    headers = inject_correlation_headers(
        {"Content-Type": "application/json", "Accept": "application/json"},
    )
    url = get_veneno_mcp_url().rstrip("/")

    try:
        with sync_http_client(timeout=get_veneno_mcp_timeout(), headers=headers) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            body = response.json()
    except httpx.HTTPError as exc:
        return {"success": False, "error": f"Veneno MCP HTTP error: {exc}", "source": "veneno-mcp", "tool": tool_name}
    except json.JSONDecodeError as exc:
        return {"success": False, "error": f"Veneno MCP invalid JSON: {exc}", "source": "veneno-mcp", "tool": tool_name}

    if "error" in body:
        err = body["error"]
        message = err.get("message", str(err)) if isinstance(err, dict) else str(err)
        return {"success": False, "error": message, "source": "veneno-mcp", "tool": tool_name}

    result = body.get("result") or {}
    text_blocks = [
        block.get("text", "")
        for block in result.get("content", [])
        if isinstance(block, dict) and block.get("type") == "text"
    ]
    combined = "\n".join(t for t in text_blocks if t).strip()
    parsed: Any = combined
    if combined:
        try:
            parsed = json.loads(combined)
        except json.JSONDecodeError:
            parsed = combined
    return {"success": True, "tool": tool_name, "result": parsed, "source": "veneno-mcp"}
