from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any, Awaitable

from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.types import Command, interrupt

from bootstrap.settings import Settings, get_settings
from cys_core.application.ports.profile_policy import ProfilePolicyPort
from cys_core.domain.policy.pure import classify_tool_risk_pure
from cys_core.domain.security.risk import parse_threshold
from cys_core.domain.workers.job_budget import JobBudgetExceeded, JobBudgetTracker
from cys_core.middleware._framework_casts import cast_tool_result
from cys_core.middleware.hitl_pause import (
    build_hitl_preview,
    register_hitl_pause,
    resume_decision_approved,
)
from cys_core.security.monitor import AgentMonitor
from cys_core.security.rate_limit import RedisRateLimiter

_MIDDLEWARE_BLOCK_PREFIXES = (
    "Only one tool call per turn",
    "investigate_incident already completed",
    "SIEM ladder complete",
    "Veil tool budget exhausted",
    "SIEM/Veil ladder complete",
    "Duplicate tool call blocked",
)


def _middleware_blocked_tool_result(result: Any) -> bool:
    if not isinstance(result, ToolMessage):
        return False
    if getattr(result, "status", None) != "error":
        return False
    content = str(getattr(result, "content", "") or "")
    return any(content.startswith(prefix) for prefix in _MIDDLEWARE_BLOCK_PREFIXES)


_shared_rate_limiter: RedisRateLimiter | None = None


def _get_shared_rate_limiter() -> RedisRateLimiter:
    """One Redis connection (and one blocking `.ping()`) per process, not per agent build.

    SecurityMiddleware is re-instantiated for every job's agent (a sync constructor called
    unwrapped from the async build path); constructing a fresh RedisRateLimiter each time
    re-pings Redis synchronously on every job. Caching amortizes that cost to once per process.
    """
    global _shared_rate_limiter
    if _shared_rate_limiter is None:
        _shared_rate_limiter = RedisRateLimiter()
    return _shared_rate_limiter


class SecurityMiddleware(AgentMiddleware):
    """Rate limiting, monitoring, and risk-based tool gating."""

    def __init__(
        self,
        agent_id: str,
        session_id: str = "default",
        *,
        settings: Settings | None = None,
        profile_id: str = "cybersec-soc",
        policy_port: ProfilePolicyPort | None = None,
    ) -> None:
        super().__init__()
        cfg = settings or get_settings()
        self.agent_id = agent_id
        self.session_id = session_id
        self.profile_id = profile_id
        self.stage = cfg.stage
        self._policy_port = policy_port or _default_policy_port()
        anomaly = self._policy_port.get_policy(profile_id).anomaly
        self.monitor = AgentMonitor(agent_id, profile_id=profile_id, anomaly_policy=anomaly)
        self.rate_limiter = _get_shared_rate_limiter()
        self.auto_approve_threshold = parse_threshold(self._policy_port.get_hitl_threshold(profile_id))

    def _await_hitl_if_needed(self, request: ToolCallRequest) -> ToolMessage | None:
        tool_name = request.tool_call.get("name", "")
        risk = classify_tool_risk_pure(tool_name, self._policy_port.get_policy(self.profile_id))
        if risk <= self.auto_approve_threshold:
            return None
        if self.stage == "dev":
            return ToolMessage(
                content=f"Tool '{tool_name}' (risk={risk.value}) requires human approval.",
                tool_call_id=request.tool_call.get("id", ""),
                status="error",
            )

        preview = build_hitl_preview(
            tool_name=tool_name,
            tool_args=request.tool_call.get("args", {}),
            risk_level=risk.value,
            session_id=self.session_id,
            persona=self.agent_id,
        )
        register_hitl_pause(preview)
        decision = interrupt(preview)
        if not resume_decision_approved(decision):
            return ToolMessage(
                content=f"Tool '{tool_name}' rejected by human reviewer.",
                tool_call_id=request.tool_call.get("id", ""),
                status="error",
            )
        return None

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command[Any]],
    ) -> ToolMessage | Command[Any]:
        tool_name = request.tool_call.get("name", "")
        try:
            JobBudgetTracker.check_tool_call(self.session_id)
        except JobBudgetExceeded as exc:
            return ToolMessage(
                content=str(exc),
                tool_call_id=request.tool_call.get("id", ""),
                status="error",
            )
        try:
            self.rate_limiter.check(f"{self.session_id}:{tool_name}")
        except Exception as exc:
            self.monitor.log_security_event(self.session_id, "rate_limit_exceeded", "WARNING", {"tool": tool_name})
            return ToolMessage(
                content=str(exc),
                tool_call_id=request.tool_call.get("id", ""),
                status="error",
            )

        hitl_block = self._await_hitl_if_needed(request)
        if hitl_block is not None:
            return hitl_block

        try:
            result = handler(request)
            if not _middleware_blocked_tool_result(result):
                JobBudgetTracker.record_tool_call(self.session_id)
            self.monitor.log_tool_call(
                self.session_id,
                tool_name,
                request.tool_call.get("args", {}),
                {"status": "ok"},
            )
            return cast_tool_result(result)
        except JobBudgetExceeded as exc:
            return ToolMessage(
                content=str(exc),
                tool_call_id=request.tool_call.get("id", ""),
                status="error",
            )
        except Exception as exc:
            self.monitor.log_security_event(
                self.session_id,
                "tool_failure",
                "WARNING",
                {"tool": tool_name, "error": str(exc)},
            )
            raise

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]] | ToolMessage | Command[Any]],
    ) -> ToolMessage | Command[Any]:
        tool_name = request.tool_call.get("name", "")
        try:
            JobBudgetTracker.check_tool_call(self.session_id)
        except JobBudgetExceeded as exc:
            return ToolMessage(
                content=str(exc),
                tool_call_id=request.tool_call.get("id", ""),
                status="error",
            )
        try:
            await self.rate_limiter.acheck(f"{self.session_id}:{tool_name}")
        except Exception as exc:
            self.monitor.log_security_event(self.session_id, "rate_limit_exceeded", "WARNING", {"tool": tool_name})
            return ToolMessage(
                content=str(exc),
                tool_call_id=request.tool_call.get("id", ""),
                status="error",
            )

        hitl_block = self._await_hitl_if_needed(request)
        if hitl_block is not None:
            return hitl_block

        try:
            result = handler(request)
            if inspect.isawaitable(result):
                result = await result
            if not _middleware_blocked_tool_result(result):
                JobBudgetTracker.record_tool_call(self.session_id)
            self.monitor.log_tool_call(
                self.session_id,
                tool_name,
                request.tool_call.get("args", {}),
                {"status": "ok"},
            )
            return cast_tool_result(result)
        except JobBudgetExceeded as exc:
            return ToolMessage(
                content=str(exc),
                tool_call_id=request.tool_call.get("id", ""),
                status="error",
            )
        except Exception as exc:
            self.monitor.log_security_event(
                self.session_id,
                "tool_failure",
                "WARNING",
                {"tool": tool_name, "error": str(exc)},
            )
            raise


def _default_policy_port() -> ProfilePolicyPort:
    from bootstrap.container import get_container

    return get_container().get_profile_policy_port()
