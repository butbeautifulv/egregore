from __future__ import annotations

import json
from typing import Any

import httpx

from bootstrap.settings import settings

# Read-only Veil knowledge graph + playbook tools exposed to egregore agents.
VEIL_MCP_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "ti_list_categories",
        "ti_list_kinds_in_category",
        "ti_nodes_by_category",
        "ti_search_in_category",
        "ti_get_node",
        "ti_neighbors",
        "ti_health",
        "playbook_search",
        "playbook_get",
        "playbook_procedure",
        "playbook_for_technique",
        "playbook_framework",
        "playbook_subdomains",
        "playbook_ontology_subdomains",
    }
)


class VeilMcpError(Exception):
    """Veil MCP request failed."""


def veil_mcp_enabled() -> bool:
    return settings.veil_mcp_enabled


def call_veil_mcp_tool(tool_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """Invoke one Veil MCP tool via streamable HTTP (POST /mcp, tools/call)."""
    if not veil_mcp_enabled():
        return {"success": False, "error": "Veil MCP disabled (VEIL_MCP_ENABLED=false)", "source": "veil-mcp"}
    if tool_name not in VEIL_MCP_TOOL_NAMES:
        return {"success": False, "error": f"Veil tool not allowlisted: {tool_name}", "source": "veil-mcp"}

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments or {}},
    }
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    url = settings.veil_mcp_url.rstrip("/")

    try:
        with httpx.Client(timeout=settings.veil_mcp_timeout) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            body = response.json()
    except httpx.HTTPError as exc:
        return {"success": False, "error": f"Veil MCP HTTP error: {exc}", "source": "veil-mcp", "tool": tool_name}
    except json.JSONDecodeError as exc:
        return {"success": False, "error": f"Veil MCP invalid JSON: {exc}", "source": "veil-mcp", "tool": tool_name}

    if "error" in body:
        err = body["error"]
        message = err.get("message", str(err)) if isinstance(err, dict) else str(err)
        return {"success": False, "error": message, "source": "veil-mcp", "tool": tool_name}

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

    return {
        "success": True,
        "source": "veil-mcp",
        "tool": tool_name,
        "content": parsed,
        "readonly": True,
    }
