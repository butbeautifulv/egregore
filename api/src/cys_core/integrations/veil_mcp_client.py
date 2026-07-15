from __future__ import annotations

import json
from typing import Any

import httpx
import structlog

from cys_core.application.runs.tool_coercion import (
    prepare_veil_tool_invocation,
    veil_playbook_id_hint,
    veil_technique_id_hint,
    veil_ti_category_hint,
)
from cys_core.application.runtime_config import (
    configure_from_settings,
    get_veil_mcp_timeout,
    get_veil_mcp_url,
    veil_mcp_enabled as _veil_mcp_enabled,
)
from cys_core.infrastructure.http_client import async_http_client, sync_http_client
from cys_core.observability.metrics import metrics
from cys_core.observability.tracing import inject_correlation_headers

logger = structlog.get_logger(__name__)

def _ensure_veil_runtime_config() -> None:
    """Load settings into runtime_config when MCP is called outside the composition root."""
    from cys_core.application.runtime_config import get_postgres_url

    if get_postgres_url():
        return
    from bootstrap.settings import get_settings

    configure_from_settings(get_settings())


def _classify_http_error(exc: httpx.HTTPError) -> str:
    if isinstance(exc, httpx.TimeoutException):
        return "timeout"
    if isinstance(exc, httpx.HTTPStatusError):
        if exc.response.status_code in (401, 403):
            return "auth_error"
        return "remote_error"
    if isinstance(exc, httpx.ConnectError):
        return "unavailable"
    return "remote_error"


def _classify_rpc_error(message: str) -> str:
    lower = message.lower()
    if "unknown category" in lower or "is required" in lower or "validation" in lower:
        return "invalid_args"
    if "not found" in lower:
        return "empty_result"
    return "remote_error"


def _log_veil_failure(tool_name: str, *, reason: str, error: str) -> None:
    logger.warning("veil_mcp_tool_failed", tool=tool_name, source="veil-mcp", reason=reason, error=error)

from cys_core.domain.tools.catalog.veil import VEIL_TOOL_NAMES as FALLBACK_VEIL_TOOL_NAMES

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


def _mcp_request_payload(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }


def _finalize_veil_mcp_result(tool_name: str, body: dict[str, Any]) -> dict[str, Any]:
    if "error" in body:
        err = body["error"]
        message = err.get("message", str(err)) if isinstance(err, dict) else str(err)
        reason = _classify_rpc_error(message)
        metrics.record_tool_invocation(tool_name, success=False)
        _log_veil_failure(tool_name, reason=reason, error=message)
        return {
            "success": False,
            "error": message
            + veil_playbook_id_hint(tool_name, message)
            + veil_technique_id_hint(tool_name, message)
            + veil_ti_category_hint(tool_name, message),
            "source": "veil-mcp",
            "tool": tool_name,
            "reason": reason,
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


def _prepare_veil_call(tool_name: str, arguments: dict[str, Any] | None) -> dict[str, Any] | None:
    _ensure_veil_runtime_config()
    if not veil_mcp_enabled():
        return {"success": False, "error": "Veil MCP disabled (VEIL_MCP_ENABLED=false)", "source": "veil-mcp", "reason": "unavailable"}
    if tool_name not in get_veil_allowed_tools():
        return {
            "success": False,
            "error": f"Veil tool not allowlisted: {tool_name}",
            "source": "veil-mcp",
            "reason": "invalid_args",
        }
    prepared = prepare_veil_tool_invocation(tool_name, arguments or {})
    if "arguments" not in prepared:
        metrics.record_tool_invocation(tool_name, success=False)
        reason = str(prepared.get("reason", "invalid_args"))
        _log_veil_failure(tool_name, reason=reason, error=str(prepared.get("error", "")))
        return prepared
    return prepared


def call_veil_mcp_tool(tool_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """Invoke one Veil MCP tool via streamable HTTP (POST /mcp, tools/call)."""
    prepared = _prepare_veil_call(tool_name, arguments)
    if prepared is None or "arguments" not in prepared:
        return prepared or {"success": False, "error": "invalid_args", "source": "veil-mcp"}

    payload = _mcp_request_payload(tool_name, prepared["arguments"])
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
        reason = _classify_http_error(exc)
        metrics.record_tool_invocation(tool_name, success=False)
        _log_veil_failure(tool_name, reason=reason, error=str(exc))
        return {
            "success": False,
            "error": f"Veil MCP HTTP error: {exc}",
            "source": "veil-mcp",
            "tool": tool_name,
            "reason": reason,
        }
    except json.JSONDecodeError as exc:
        metrics.record_tool_invocation(tool_name, success=False)
        _log_veil_failure(tool_name, reason="remote_error", error=str(exc))
        return {
            "success": False,
            "error": f"Veil MCP invalid JSON: {exc}",
            "source": "veil-mcp",
            "tool": tool_name,
            "reason": "remote_error",
        }

    return _finalize_veil_mcp_result(tool_name, body)


async def acall_veil_mcp_tool(tool_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """Async Veil MCP invocation for worker event-loop contexts."""
    prepared = _prepare_veil_call(tool_name, arguments)
    if prepared is None or "arguments" not in prepared:
        return prepared or {"success": False, "error": "invalid_args", "source": "veil-mcp"}

    payload = _mcp_request_payload(tool_name, prepared["arguments"])
    headers = inject_correlation_headers(
        {"Content-Type": "application/json", "Accept": "application/json"},
    )
    url = get_veil_mcp_url().rstrip("/")

    try:
        async with async_http_client(timeout=get_veil_mcp_timeout(), headers=headers) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            body = response.json()
    except httpx.HTTPError as exc:
        reason = _classify_http_error(exc)
        metrics.record_tool_invocation(tool_name, success=False)
        _log_veil_failure(tool_name, reason=reason, error=str(exc))
        return {
            "success": False,
            "error": f"Veil MCP HTTP error: {exc}",
            "source": "veil-mcp",
            "tool": tool_name,
            "reason": reason,
        }
    except json.JSONDecodeError as exc:
        metrics.record_tool_invocation(tool_name, success=False)
        _log_veil_failure(tool_name, reason="remote_error", error=str(exc))
        return {
            "success": False,
            "error": f"Veil MCP invalid JSON: {exc}",
            "source": "veil-mcp",
            "tool": tool_name,
            "reason": "remote_error",
        }

    return _finalize_veil_mcp_result(tool_name, body)
