from __future__ import annotations

import hashlib
import inspect
import json
import structlog
from collections.abc import Callable
from typing import Any, Awaitable

from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.types import Command

from cys_core.middleware._framework_casts import cast_tool_result

logger = structlog.get_logger(__name__)

_TRIAGE_PERSONAS = frozenset({"soc", "intel"})
_MAX_DUPLICATE_CALLS = 2
_dedup_counts: dict[str, dict[str, int]] = {}


def clear_tool_dedup(job_id: str) -> None:
    if job_id:
        _dedup_counts.pop(job_id, None)


def _canonical_args(args: dict[str, Any]) -> str:
    return json.dumps(args, sort_keys=True, default=str)


def _call_hash(tool_name: str, args: dict[str, Any]) -> str:
    digest = hashlib.sha256(f"{tool_name}:{_canonical_args(args)}".encode()).hexdigest()
    return digest[:16]


class ToolDedupMiddleware(AgentMiddleware):
    """Block repeated identical tool calls within one worker job (triage personas)."""

    def __init__(self, *, persona: str) -> None:
        super().__init__()
        self.persona = persona

    def _job_id(self) -> str:
        job_id = structlog.contextvars.get_contextvars().get("job_id")
        return job_id if isinstance(job_id, str) else ""

    def _check(self, request: ToolCallRequest) -> ToolMessage | None:
        if self.persona not in _TRIAGE_PERSONAS:
            return None
        tool_name = str(request.tool_call.get("name", ""))
        if not tool_name:
            return None
        job_id = self._job_id()
        if not job_id:
            return None
        raw_args = request.tool_call.get("args", {})
        args = raw_args if isinstance(raw_args, dict) else {}
        call_key = _call_hash(tool_name, args)
        bucket = _dedup_counts.setdefault(job_id, {})
        prior = bucket.get(call_key, 0)
        if prior >= _MAX_DUPLICATE_CALLS:
            logger.info(
                "tool_dedup_blocked",
                tool=tool_name,
                persona=self.persona,
                job_id=job_id,
                attempt=prior + 1,
                args_hash=call_key,
            )
            return ToolMessage(
                content=(
                    "Duplicate tool call blocked; try a different approach or "
                    "emit the persona finding JSON with data_gaps if evidence is sparse."
                ),
                tool_call_id=request.tool_call.get("id", ""),
                status="error",
            )
        bucket[call_key] = prior + 1
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
