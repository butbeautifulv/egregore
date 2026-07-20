from __future__ import annotations

import json
from typing import Any

import httpx
import structlog

from cys_core.application.runs.tool_coercion import normalize_siem_tool_args
from cys_core.application.runtime_config import (
    get_siem_mcp_timeout,
    get_siem_mcp_url,
)
from cys_core.application.runtime_config import (
    siem_mcp_enabled as _siem_mcp_enabled,
)
from cys_core.domain.tools.catalog.siem import SIEM_TOOL_NAMES as FALLBACK_SIEM_TOOL_NAMES
from cys_core.integrations.mcp_http import (
    build_tools_call_payload,
    finalize_mcp_result,
    invoke_mcp_async,
    invoke_mcp_sync,
)
from cys_core.observability.metrics import metrics
from cys_core.observability.tracing import inject_correlation_headers

logger = structlog.get_logger(__name__)

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


def _mcp_content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if content is not None:
        return json.dumps(content, ensure_ascii=False)
    return ""


def _mcp_validation_error_message(content: Any) -> str | None:
    text = _mcp_content_text(content)
    if "validation error for call[" in text.lower():
        return text
    return None


def _mcp_tool_error_message(content: Any) -> str | None:
    validation = _mcp_validation_error_message(content)
    if validation is not None:
        return validation
    text = _mcp_content_text(content)
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


def _siem_mcp_request_payload(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return build_tools_call_payload(tool_name, arguments)


def _siem_mcp_headers() -> dict[str, str]:
    return inject_correlation_headers(
        {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
    )


def _finalize_siem_mcp_result(tool_name: str, body: dict[str, Any]) -> dict[str, Any]:
    def _on_success(name: str) -> None:
        metrics.record_tool_invocation(name, success=True)
        logger.info("siem_mcp_tool_ok", tool=name, source="siem-mcp")

    def _on_failure(name: str) -> None:
        metrics.record_tool_invocation(name, success=False)

    def _validation(content: Any) -> str | None:
        return _mcp_tool_error_message(content)

    result = finalize_mcp_result(
        tool_name,
        body,
        source="siem-mcp",
        hint_fn=_siem_pdql_hint,
        validation_fn=_validation,
        on_success=_on_success,
        on_failure=_on_failure,
    )
    if not result.get("success"):
        logger.warning(
            "siem_mcp_tool_failed",
            tool=tool_name,
            source="siem-mcp",
            error=str(result.get("error", ""))[:500],
        )
    return result


def _prepare_siem_call(tool_name: str, arguments: dict[str, Any] | None) -> dict[str, Any] | None:
    if not siem_mcp_enabled():
        return {"success": False, "error": "SIEM MCP disabled (SIEM_MCP_ENABLED=false)", "source": "siem-mcp"}
    if tool_name not in get_siem_allowed_tools():
        return {"success": False, "error": f"SIEM tool not allowlisted: {tool_name}", "source": "siem-mcp"}
    return {"arguments": normalize_siem_tool_args(tool_name, arguments or {})}


def call_siem_mcp_tool(tool_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """Invoke one MaxPatrol SIEM MCP tool via streamable HTTP (POST /mcp, tools/call)."""
    prepared = _prepare_siem_call(tool_name, arguments)
    if prepared is None or "arguments" not in prepared:
        return prepared or {"success": False, "error": "invalid_args", "source": "siem-mcp"}

    payload = _siem_mcp_request_payload(tool_name, prepared["arguments"])
    url = get_siem_mcp_url().rstrip("/")

    try:
        body = invoke_mcp_sync(
            url=url,
            payload=payload,
            headers=_siem_mcp_headers(),
            timeout=get_siem_mcp_timeout(),
        )
    except httpx.HTTPError as exc:
        metrics.record_tool_invocation(tool_name, success=False)
        logger.warning("siem_mcp_http_error", tool=tool_name, source="siem-mcp", error=str(exc))
        hint = _siem_pdql_hint(tool_name, str(exc))
        return {
            "success": False,
            "error": f"SIEM MCP HTTP error: {exc}{hint}",
            "source": "siem-mcp",
            "tool": tool_name,
        }
    except json.JSONDecodeError as exc:
        metrics.record_tool_invocation(tool_name, success=False)
        logger.warning("siem_mcp_invalid_json", tool=tool_name, source="siem-mcp", error=str(exc))
        return {"success": False, "error": f"SIEM MCP invalid JSON: {exc}", "source": "siem-mcp", "tool": tool_name}

    return _finalize_siem_mcp_result(tool_name, body)


async def acall_siem_mcp_tool(tool_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """Async SIEM MCP invocation for worker event-loop contexts."""
    prepared = _prepare_siem_call(tool_name, arguments)
    if prepared is None or "arguments" not in prepared:
        return prepared or {"success": False, "error": "invalid_args", "source": "siem-mcp"}

    payload = _siem_mcp_request_payload(tool_name, prepared["arguments"])
    url = get_siem_mcp_url().rstrip("/")

    try:
        body = await invoke_mcp_async(
            url=url,
            payload=payload,
            headers=_siem_mcp_headers(),
            timeout=get_siem_mcp_timeout(),
        )
    except httpx.HTTPError as exc:
        metrics.record_tool_invocation(tool_name, success=False)
        logger.warning("siem_mcp_http_error", tool=tool_name, source="siem-mcp", error=str(exc))
        hint = _siem_pdql_hint(tool_name, str(exc))
        return {
            "success": False,
            "error": f"SIEM MCP HTTP error: {exc}{hint}",
            "source": "siem-mcp",
            "tool": tool_name,
        }
    except json.JSONDecodeError as exc:
        metrics.record_tool_invocation(tool_name, success=False)
        logger.warning("siem_mcp_invalid_json", tool=tool_name, source="siem-mcp", error=str(exc))
        return {"success": False, "error": f"SIEM MCP invalid JSON: {exc}", "source": "siem-mcp", "tool": tool_name}

    return _finalize_siem_mcp_result(tool_name, body)
