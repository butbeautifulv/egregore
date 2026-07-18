from __future__ import annotations

import json
from typing import Any

import httpx
import structlog

from cys_core.application.runtime_config import (
    get_mcp_call_max_retries,
    get_nessus_mcp_timeout,
    get_nessus_mcp_url,
)
from cys_core.application.runtime_config import (
    nessus_mcp_enabled as _nessus_mcp_enabled,
)
from cys_core.infrastructure.http_client import sync_http_client
from cys_core.integrations.mcp_http import call_with_retry
from cys_core.observability.metrics import metrics
from cys_core.observability.tracing import inject_correlation_headers

logger = structlog.get_logger(__name__)

FALLBACK_NESSUS_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "list_scans",
        "list_scan_templates",
        "create_scan",
        "launch_scan",
        "get_scan_status",
        "wait_for_scan",
        "sync_scan_inventory",
        "lookup_asset_by_ip",
        "search_inventory",
        "get_asset_vuln_summary",
        "get_asset_findings",
        "list_high_risk_assets",
        "search_api_docs",
    }
)

NESSUS_MCP_TOOL_NAMES = FALLBACK_NESSUS_TOOL_NAMES


def get_nessus_allowed_tools(profile_id: str = "cybersec-hunter") -> frozenset[str]:
    try:
        from cys_core.infrastructure.catalog.registry_factory import get_mcp_catalog

        tools: set[str] = set()
        for server in get_mcp_catalog().list_servers(profile_id=profile_id, enabled_only=True):
            if server.id == "nessus" or "tenable" in server.url.lower() or "nessus" in server.url.lower():
                if server.allowed_tools:
                    tools.update(server.allowed_tools)
        if tools:
            return frozenset(tools)
    except Exception:
        pass
    return FALLBACK_NESSUS_TOOL_NAMES


class NessusMcpError(Exception):
    """Nessus MCP request failed."""


def nessus_mcp_enabled() -> bool:
    return _nessus_mcp_enabled()


def _mcp_content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if content is not None:
        return json.dumps(content, ensure_ascii=False)
    return ""


def _mcp_tool_error_message(content: Any) -> str | None:
    text = _mcp_content_text(content)
    lower = text.lower()
    if "validation error for call[" in lower:
        return text
    if "error calling tool" in lower or "nessus api error" in lower:
        return text
    return None


def call_nessus_mcp_tool(tool_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """Invoke one Nessus MCP tool via streamable HTTP (POST /mcp, tools/call)."""
    if not nessus_mcp_enabled():
        return {"success": False, "error": "Nessus MCP disabled (NESSUS_MCP_ENABLED=false)", "source": "nessus-mcp"}
    if tool_name not in get_nessus_allowed_tools():
        return {"success": False, "error": f"Nessus tool not allowlisted: {tool_name}", "source": "nessus-mcp"}

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments or {}},
    }
    headers = inject_correlation_headers(
        {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
    )
    url = get_nessus_mcp_url().rstrip("/")

    def _call() -> dict[str, Any]:
        with sync_http_client(timeout=get_nessus_mcp_timeout(), headers=headers) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            return response.json()

    try:
        body = call_with_retry(_call, max_retries=get_mcp_call_max_retries(), source="nessus-mcp")
    except httpx.HTTPError as exc:
        metrics.record_tool_invocation(tool_name, success=False)
        logger.warning("nessus_mcp_http_error", tool=tool_name, source="nessus-mcp", error=str(exc))
        return {"success": False, "error": f"Nessus MCP HTTP error: {exc}", "source": "nessus-mcp", "tool": tool_name}
    except json.JSONDecodeError as exc:
        metrics.record_tool_invocation(tool_name, success=False)
        logger.warning("nessus_mcp_invalid_json", tool=tool_name, source="nessus-mcp", error=str(exc))
        return {"success": False, "error": f"Nessus MCP invalid JSON: {exc}", "source": "nessus-mcp", "tool": tool_name}

    if "error" in body:
        err = body["error"]
        message = err.get("message", str(err)) if isinstance(err, dict) else str(err)
        metrics.record_tool_invocation(tool_name, success=False)
        logger.warning("nessus_mcp_rpc_error", tool=tool_name, source="nessus-mcp", error=message)
        return {"success": False, "error": message, "source": "nessus-mcp", "tool": tool_name}

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

    validation_error = _mcp_tool_error_message(parsed)
    if validation_error is None and isinstance(parsed, dict):
        validation_error = _mcp_tool_error_message(parsed.get("content"))
    if validation_error is not None:
        metrics.record_tool_invocation(tool_name, success=False)
        return {
            "success": False,
            "error": validation_error,
            "source": "nessus-mcp",
            "tool": tool_name,
            "content": parsed,
        }

    metrics.record_tool_invocation(tool_name, success=True)
    logger.info("nessus_mcp_tool_ok", tool=tool_name, source="nessus-mcp")
    return {
        "success": True,
        "source": "nessus-mcp",
        "tool": tool_name,
        "content": parsed,
        "readonly": True,
    }
