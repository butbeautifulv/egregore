from __future__ import annotations

import json
from typing import Any

import httpx
import structlog

from cys_core.application.runtime_config import (
    get_siem_mcp_timeout,
    get_siem_mcp_url,
    siem_mcp_enabled as _siem_mcp_enabled,
)
from cys_core.application.runs.tool_coercion import normalize_siem_tool_args
from cys_core.infrastructure.http_client import sync_http_client
from cys_core.observability.metrics import metrics
from cys_core.observability.tracing import inject_correlation_headers

logger = structlog.get_logger(__name__)

# Curated read-only SIEM tools for SOC persona (not full 30+ MCP surface).
FALLBACK_SIEM_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "investigate_incident",
        "list_incidents",
        "get_event_by_uuid",
        "search_events",
        "list_aggregated_events",
        "lookup_assets_by_ip",
        "export_table_list",
        "search_user_actions",
        "search_api_docs",
    }
)

SIEM_MCP_TOOL_NAMES = FALLBACK_SIEM_TOOL_NAMES


def get_siem_allowed_tools(profile_id: str = "cybersec-soc") -> frozenset[str]:
    try:
        from cys_core.infrastructure.catalog.registry_factory import get_mcp_catalog

        tools: set[str] = set()
        for server in get_mcp_catalog().list_servers(profile_id=profile_id, enabled_only=True):
            if server.id == "siem" or "siem" in server.url.lower():
                if server.allowed_tools:
                    tools.update(server.allowed_tools)
        if tools:
            return frozenset(tools)
    except Exception:
        pass
    return FALLBACK_SIEM_TOOL_NAMES


class SiemMcpError(Exception):
    """SIEM MCP request failed."""


def siem_mcp_enabled() -> bool:
    return _siem_mcp_enabled()


def _mcp_validation_error_message(content: Any) -> str | None:
    text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False) if content is not None else ""
    if "validation error for call[" in text.lower():
        return text
    return None


def _mcp_tool_error_message(content: Any) -> str | None:
    validation = _mcp_validation_error_message(content)
    if validation is not None:
        return validation
    text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False) if content is not None else ""
    lower = text.lower()
    if "error calling tool" in lower or "siem api error" in lower:
        return text
    return None


def _siem_pdql_hint(tool_name: str, error: str) -> str:
    if tool_name not in ("search_events", "query_siem_readonly"):
        return ""
    lower = error.lower()
    if "pdql" not in lower and "parse.error" not in lower and "parse error" not in lower:
        return ""
    return (
        " Hint: use investigate_incident(incident_id=<uuid>) for incident triage; "
        "search_events requires valid PDQL where syntax (e.g. src.ip = '10.0.0.1'), "
        "not incident_id:INC-123."
    )


def call_siem_mcp_tool(tool_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """Invoke one MaxPatrol SIEM MCP tool via streamable HTTP (POST /mcp, tools/call)."""
    if not siem_mcp_enabled():
        return {"success": False, "error": "SIEM MCP disabled (SIEM_MCP_ENABLED=false)", "source": "siem-mcp"}
    if tool_name not in get_siem_allowed_tools():
        return {"success": False, "error": f"SIEM tool not allowlisted: {tool_name}", "source": "siem-mcp"}

    normalized_arguments = normalize_siem_tool_args(tool_name, arguments or {})

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": normalized_arguments},
    }
    headers = inject_correlation_headers(
        {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
    )
    url = get_siem_mcp_url().rstrip("/")

    try:
        with sync_http_client(timeout=get_siem_mcp_timeout(), headers=headers) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            body = response.json()
    except httpx.HTTPError as exc:
        metrics.record_tool_invocation(tool_name, success=False)
        logger.warning("siem_mcp_http_error", tool=tool_name, source="siem-mcp", error=str(exc))
        return {"success": False, "error": f"SIEM MCP HTTP error: {exc}{_siem_pdql_hint(tool_name, str(exc))}", "source": "siem-mcp", "tool": tool_name}
    except json.JSONDecodeError as exc:
        metrics.record_tool_invocation(tool_name, success=False)
        logger.warning("siem_mcp_invalid_json", tool=tool_name, source="siem-mcp", error=str(exc))
        return {"success": False, "error": f"SIEM MCP invalid JSON: {exc}", "source": "siem-mcp", "tool": tool_name}

    if "error" in body:
        err = body["error"]
        message = err.get("message", str(err)) if isinstance(err, dict) else str(err)
        metrics.record_tool_invocation(tool_name, success=False)
        logger.warning("siem_mcp_rpc_error", tool=tool_name, source="siem-mcp", error=message)
        return {"success": False, "error": message + _siem_pdql_hint(tool_name, message), "source": "siem-mcp", "tool": tool_name}

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
        nested = parsed.get("content")
        validation_error = _mcp_tool_error_message(nested)
    if validation_error is not None:
        metrics.record_tool_invocation(tool_name, success=False)
        logger.warning(
            "siem_mcp_tool_validation_error",
            tool=tool_name,
            source="siem-mcp",
            error=validation_error[:500],
        )
        return {
            "success": False,
            "error": validation_error + _siem_pdql_hint(tool_name, validation_error),
            "source": "siem-mcp",
            "tool": tool_name,
            "content": parsed,
        }

    metrics.record_tool_invocation(tool_name, success=True)
    logger.info("siem_mcp_tool_ok", tool=tool_name, source="siem-mcp")
    return {
        "success": True,
        "source": "siem-mcp",
        "tool": tool_name,
        "content": parsed,
        "readonly": True,
    }
