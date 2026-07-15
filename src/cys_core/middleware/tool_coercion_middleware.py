from __future__ import annotations

import inspect
import json
import structlog
from collections.abc import Callable
from typing import Any, Awaitable

from langchain.agents.middleware.types import AgentMiddleware
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.types import Command

from cys_core.application.runs.tool_coercion import (
    coerce_tool_args,
    normalize_siem_tool_args,
    normalize_veil_tool_args,
)
from cys_core.application.workers.tool_execution_tracker import (
    ingest_tool_output_manifest,
    record_siem_drilldown,
    record_tool_call,
    record_tool_execution,
    record_tool_output,
    record_tool_success,
    record_veil_tool,
)
from cys_core.infrastructure.tools.adapters.siem_mcp import is_siem_tool
from cys_core.infrastructure.tools.adapters.veil_mcp import is_veil_tool

logger = structlog.get_logger(__name__)

_INTEL_SUCCESS_TOOLS = frozenset({"enrich_ioc", "ti_search_in_category", "playbook_search"})
_SIEM_DRILLDOWN_TOOLS = frozenset({"search_events", "get_event_by_uuid", "list_incident_events"})


def _tool_result_text(result: Any) -> str:
    return str(getattr(result, "content", result) or "")


def _tool_result_ok(result: Any) -> bool:
    status = getattr(result, "status", None)
    if status == "error":
        return False
    text = _tool_result_text(result)
    if not text.strip():
        return False
    lower = text.lower()
    if "error calling tool" in lower:
        return False
    if '"success": false' in lower or '"success":false' in lower:
        return False
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            if payload.get("success") is False:
                return False
            if payload.get("error"):
                return False
    except json.JSONDecodeError:
        pass
    return True


class ToolCoercionMiddleware(AgentMiddleware):
    """Coerce tool call arguments before handler execution."""

    def _record(self, tool_name: str) -> None:
        job_id = structlog.contextvars.get_contextvars().get("job_id")
        if isinstance(job_id, str) and job_id:
            record_tool_execution(job_id)
            record_tool_call(job_id, tool_name)

    def _normalize_args(self, request: ToolCallRequest) -> None:
        raw_args = request.tool_call.get("args", {})
        if not isinstance(raw_args, dict):
            return
        tool_name = str(request.tool_call.get("name", ""))
        if is_siem_tool(tool_name):
            request.tool_call["args"] = normalize_siem_tool_args(tool_name, raw_args)
        elif is_veil_tool(tool_name):
            request.tool_call["args"] = normalize_veil_tool_args(tool_name, raw_args)
        else:
            request.tool_call["args"] = coerce_tool_args(raw_args)

    def _record_success(self, tool_name: str, result: Any) -> None:
        job_id = structlog.contextvars.get_contextvars().get("job_id")
        if not isinstance(job_id, str) or not job_id:
            return
        text = _tool_result_text(result)
        record_tool_output(job_id, tool_name, text)
        ingest_tool_output_manifest(job_id, tool_name, text)
        if tool_name in _SIEM_DRILLDOWN_TOOLS:
            record_siem_drilldown(job_id)
        if not _tool_result_ok(result):
            return
        if tool_name == "investigate_incident":
            record_tool_success(job_id, tool_name)
            return
        if tool_name in _INTEL_SUCCESS_TOOLS or tool_name == "load_skill" or is_veil_tool(tool_name) or tool_name == "enrich_ioc":
            record_tool_success(job_id, tool_name)
        if is_veil_tool(tool_name) or tool_name == "enrich_ioc":
            record_veil_tool(job_id)

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Any],
    ) -> Any:
        self._normalize_args(request)
        tool_name = str(request.tool_call.get("name", ""))
        self._record(tool_name)
        result = handler(request)
        self._record_success(tool_name, result)
        return result

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[Any] | Any],
    ) -> Any:
        self._normalize_args(request)
        tool_name = str(request.tool_call.get("name", ""))
        self._record(tool_name)
        result = handler(request)
        if hasattr(result, "__await__"):
            result = await result
        self._record_success(tool_name, result)
        return result
