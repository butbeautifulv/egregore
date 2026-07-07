from __future__ import annotations

import json
from typing import Any

import httpx
import structlog

from cys_core.application.runs.tool_coercion import (
    normalize_veil_tool_args,
    veil_playbook_id_hint,
    veil_technique_id_hint,
    veil_ti_category_hint,
)
from cys_core.application.runtime_config import (
    get_veil_mcp_timeout,
    get_veil_mcp_url,
    veil_mcp_enabled as _veil_mcp_enabled,
)
from cys_core.infrastructure.http_client import sync_http_client
from cys_core.observability.metrics import metrics
from cys_core.observability.tracing import inject_correlation_headers

logger = structlog.get_logger(__name__)

# Read-only Veil knowledge graph + playbook tools exposed to egregore agents.
FALLBACK_VEIL_TOOL_NAMES: frozenset[str] = frozenset(
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

# Backward-compatible alias for imports that still reference the old name.
VEIL_MCP_TOOL_NAMES = FALLBACK_VEIL_TOOL_NAMES


def get_veil_allowed_tools(profile_id: str = "cybersec-soc") -> frozenset[str]:
    try:
        from cys_core.infrastructure.catalog.registry_factory import get_mcp_catalog

        tools: set[str] = set()
        for server in get_mcp_catalog().list_servers(profile_id=profile_id, enabled_only=True):
            if server.id == "veil" or "veil" in server.url.lower():
                if server.allowed_tools:
                    tools.update(server.allowed_tools)
        if tools:
            return frozenset(tools)
    except Exception:
        pass
    return FALLBACK_VEIL_TOOL_NAMES


class VeilMcpError(Exception):
    """Veil MCP request failed."""


def veil_mcp_enabled() -> bool:
    return _veil_mcp_enabled()


def call_veil_mcp_tool(tool_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """Invoke one Veil MCP tool via streamable HTTP (POST /mcp, tools/call)."""
    if not veil_mcp_enabled():
        return {"success": False, "error": "Veil MCP disabled (VEIL_MCP_ENABLED=false)", "source": "veil-mcp"}
    if tool_name not in get_veil_allowed_tools():
        return {"success": False, "error": f"Veil tool not allowlisted: {tool_name}", "source": "veil-mcp"}

    normalized_arguments = normalize_veil_tool_args(tool_name, arguments or {})

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": normalized_arguments},
    }
    headers = inject_correlation_headers(
        {"Content-Type": "application/json", "Accept": "application/json"},
    )
    url = get_veil_mcp_url().rstrip("/")

    try:
        with sync_http_client(timeout=get_veil_mcp_timeout(), headers=headers) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            body = response.json()
    except httpx.HTTPError as exc:
        metrics.record_tool_invocation(tool_name, success=False)
        logger.warning("veil_mcp_http_error", tool=tool_name, source="veil-mcp", error=str(exc))
        return {"success": False, "error": f"Veil MCP HTTP error: {exc}", "source": "veil-mcp", "tool": tool_name}
    except json.JSONDecodeError as exc:
        metrics.record_tool_invocation(tool_name, success=False)
        logger.warning("veil_mcp_invalid_json", tool=tool_name, source="veil-mcp", error=str(exc))
        return {"success": False, "error": f"Veil MCP invalid JSON: {exc}", "source": "veil-mcp", "tool": tool_name}

    if "error" in body:
        err = body["error"]
        message = err.get("message", str(err)) if isinstance(err, dict) else str(err)
        metrics.record_tool_invocation(tool_name, success=False)
        logger.warning("veil_mcp_rpc_error", tool=tool_name, source="veil-mcp", error=message)
        return {
            "success": False,
            "error": message
            + veil_playbook_id_hint(tool_name, message)
            + veil_technique_id_hint(tool_name, message)
            + veil_ti_category_hint(tool_name, message),
            "source": "veil-mcp",
            "tool": tool_name,
        }

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

    metrics.record_tool_invocation(tool_name, success=True)
    logger.info("veil_mcp_tool_ok", tool=tool_name, source="veil-mcp")
    return {
        "success": True,
        "source": "veil-mcp",
        "tool": tool_name,
        "content": parsed,
        "readonly": True,
    }
