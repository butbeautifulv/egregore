from __future__ import annotations

import inspect
import structlog
from collections.abc import Callable
from typing import Any, Awaitable

from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.types import Command

from cys_core.application.tools.providers.siem import SIEM_TOOL_NAMES
from cys_core.application.workers.tool_execution_tracker import (
    get_merged_manifest,
    get_veil_tool_count,
    is_siem_telemetry_sparse,
    siem_drilldown_budget_exhausted,
    siem_investigate_done,
    tool_succeeded,
)
from cys_core.infrastructure.tools.adapters.veil_mcp import is_veil_tool
from cys_core.middleware._framework_casts import cast_tool_result

logger = structlog.get_logger(__name__)

_TRIAGE_PERSONAS = frozenset({"soc", "intel"})
_VEIL_LADDER_TOOLS = frozenset({"enrich_ioc"})
_MAX_VEIL_TOOLS = 2
_SIEM_DRILLDOWN_WHEN_SPARSE = frozenset({"search_events", "get_event_by_uuid"})
_SIEM_ALLOWED_AFTER_INVESTIGATE = frozenset(
    {
        "get_event_by_uuid",
        "get_incident",
        "list_incident_events",
        "load_skill",
        "search_api_docs",
    }
)

# NOTE: these block messages are matched by substring in
# cys_core/application/workers/timeout_salvage.py's _LADDER_BLOCK_MARKERS to decide
# whether a cached tool output is just a ladder-block echo (not real progress) when
# building a salvage finding. Keep both in sync — see test_ladder_marker_sync.py.
_MSG_SIEM_REPEAT_BLOCKED = (
    "investigate_incident already completed. "
    "Emit SocFinding JSON citing evidence_manifest obs_id refs."
)
_MSG_SIEM_VEIL_LADDER_COMPLETE = "SIEM/Veil ladder complete. Emit SocFinding JSON now."
_MSG_SIEM_LADDER_COMPLETE = (
    "SIEM ladder complete after investigate_incident. "
    "Emit SocFinding JSON citing evidence_manifest obs_id refs."
)
_MSG_VEIL_BUDGET_EXHAUSTED = (
    f"Veil tool budget exhausted ({_MAX_VEIL_TOOLS} max). Emit the persona finding JSON now."
)


def _is_veil_ladder_tool(tool_name: str) -> bool:
    return is_veil_tool(tool_name) or tool_name in _VEIL_LADDER_TOOLS


class ToolLadderMiddleware(AgentMiddleware):
    """Enforce SIEM/Veil tool budgets for triage personas (soc, intel)."""

    def __init__(self, *, persona: str) -> None:
        super().__init__()
        self.persona = persona

    def _job_id(self) -> str:
        job_id = structlog.contextvars.get_contextvars().get("job_id")
        return job_id if isinstance(job_id, str) else ""

    def _investigation_id(self) -> str:
        ctx = structlog.contextvars.get_contextvars()
        for key in ("correlation_id", "investigation_id"):
            value = ctx.get(key)
            if isinstance(value, str) and value:
                return value
        return ""

    def _siem_investigate_done(self, job_id: str) -> bool:
        return siem_investigate_done(job_id, self._investigation_id(), persona=self.persona)

    def _blocked(self, request: ToolCallRequest, message: str) -> ToolMessage:
        return ToolMessage(
            content=message,
            tool_call_id=request.tool_call.get("id", ""),
            status="error",
        )

    def _check(self, request: ToolCallRequest) -> ToolMessage | None:
        if self.persona not in _TRIAGE_PERSONAS:
            return None
        tool_name = str(request.tool_call.get("name", ""))
        if not tool_name:
            return None
        job_id = self._job_id()

        if self.persona == "soc" and tool_name in SIEM_TOOL_NAMES:
            if self._siem_investigate_done(job_id):
                if tool_name == "investigate_incident":
                    logger.info(
                        "tool_ladder_siem_repeat_blocked",
                        tool=tool_name,
                        persona=self.persona,
                        job_id=job_id,
                    )
                    return self._blocked(request, _MSG_SIEM_REPEAT_BLOCKED)
                sparse = is_siem_telemetry_sparse(job_id)
                if (
                    sparse
                    and tool_name in _SIEM_DRILLDOWN_WHEN_SPARSE
                    and not siem_drilldown_budget_exhausted(job_id)
                ):
                    return None
                if tool_name in _SIEM_ALLOWED_AFTER_INVESTIGATE:
                    if tool_name == "load_skill" and (
                        get_veil_tool_count(job_id) >= _MAX_VEIL_TOOLS
                        or siem_drilldown_budget_exhausted(job_id)
                    ):
                        return self._blocked(request, _MSG_SIEM_VEIL_LADDER_COMPLETE)
                    return None
                manifest = get_merged_manifest(job_id)
                logger.info(
                    "tool_ladder_siem_blocked",
                    tool=tool_name,
                    persona=self.persona,
                    job_id=job_id,
                    telemetry_level=getattr(manifest, "telemetry_level", None),
                )
                return self._blocked(request, _MSG_SIEM_LADDER_COMPLETE)
            if tool_name in _SIEM_ALLOWED_AFTER_INVESTIGATE:
                return None
            sparse = is_siem_telemetry_sparse(job_id)
            if (
                sparse
                and tool_name in _SIEM_DRILLDOWN_WHEN_SPARSE
                and not siem_drilldown_budget_exhausted(job_id)
            ):
                return None

        if (
            self.persona == "soc"
            and tool_name == "load_skill"
            and self._siem_investigate_done(job_id)
            and (
                get_veil_tool_count(job_id) >= _MAX_VEIL_TOOLS
                or siem_drilldown_budget_exhausted(job_id)
            )
        ):
            return self._blocked(request, _MSG_SIEM_VEIL_LADDER_COMPLETE)

        if _is_veil_ladder_tool(tool_name) and get_veil_tool_count(job_id) >= _MAX_VEIL_TOOLS:
            logger.info(
                "tool_ladder_veil_blocked",
                tool=tool_name,
                persona=self.persona,
                job_id=job_id,
                veil_calls=get_veil_tool_count(job_id),
            )
            return self._blocked(request, _MSG_VEIL_BUDGET_EXHAUSTED)
        return None

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command[Any]],
    ) -> ToolMessage | Command[Any]:
        blocked = self._check(request)
        if blocked is not None:
            return blocked
        return handler(request)

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]] | ToolMessage | Command[Any]],
    ) -> ToolMessage | Command[Any]:
        blocked = self._check(request)
        if blocked is not None:
            return blocked
        result = handler(request)
        if inspect.isawaitable(result):
            return cast_tool_result(await result)
        return cast_tool_result(result)
