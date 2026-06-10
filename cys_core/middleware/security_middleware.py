from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langchain.agents.middleware.human_in_the_loop import HumanInTheLoopMiddleware
from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.types import Command

from config import settings
from cys_core.security.monitor import AgentMonitor
from cys_core.security.rate_limit import RedisRateLimiter
from cys_core.security.risk import RiskLevel, classify_tool_risk, parse_threshold


class SecurityMiddleware(AgentMiddleware):
    """Rate limiting, monitoring, and risk-based tool gating."""

    def __init__(self, agent_id: str, session_id: str = "default") -> None:
        super().__init__()
        self.agent_id = agent_id
        self.session_id = session_id
        self.monitor = AgentMonitor(agent_id)
        self.rate_limiter = RedisRateLimiter()
        self.auto_approve_threshold = parse_threshold(settings.hitl_auto_approve_threshold)

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command[Any]],
    ) -> ToolMessage | Command[Any]:
        tool_name = request.tool_call.get("name", "")
        try:
            self.rate_limiter.check(f"{self.session_id}:{tool_name}")
        except Exception as exc:
            self.monitor.log_security_event(
                self.session_id, "rate_limit_exceeded", "WARNING", {"tool": tool_name}
            )
            return ToolMessage(
                content=str(exc),
                tool_call_id=request.tool_call.get("id", ""),
                status="error",
            )

        risk = classify_tool_risk(tool_name)
        if risk > self.auto_approve_threshold and settings.stage != "dev":
            return ToolMessage(
                content=f"Tool '{tool_name}' (risk={risk.value}) requires human approval.",
                tool_call_id=request.tool_call.get("id", ""),
                status="error",
            )

        try:
            result = handler(request)
            self.monitor.log_tool_call(
                self.session_id,
                tool_name,
                request.tool_call.get("args", {}),
                {"status": "ok"},
            )
            return result
        except Exception as exc:
            self.monitor.log_security_event(
                self.session_id,
                "tool_failure",
                "WARNING",
                {"tool": tool_name, "error": str(exc)},
            )
            raise


def build_hitl_middleware(interrupt_tools: dict[str, bool]) -> HumanInTheLoopMiddleware:
    """Build HITL middleware for sensitive tools."""
    interrupt_on = {
        name: {"allowed_decisions": ["approve", "edit", "reject"]}
        for name, enabled in interrupt_tools.items()
        if enabled
    }
    return HumanInTheLoopMiddleware(interrupt_on=interrupt_on)
