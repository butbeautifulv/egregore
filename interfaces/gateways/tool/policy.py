from __future__ import annotations

from dataclasses import dataclass

from bootstrap.settings import settings
from cys_core.domain.security.risk import RiskLevel, classify_tool_risk
from interfaces.gateways.tool.models import ToolInvokeRequest


class ToolChainDepthExceeded(Exception):
    """Raised when sequential high-risk tool chain exceeds policy limit."""


@dataclass
class ToolChainState:
    consecutive_high_risk: int = 0


_chains: dict[str, ToolChainState] = {}


def _chain_key(request: ToolInvokeRequest) -> str:
    return request.job_id or request.sandbox_id


def is_high_risk_tool(tool_name: str) -> bool:
    return classify_tool_risk(tool_name) >= RiskLevel.HIGH


def check_tool_chain(request: ToolInvokeRequest) -> None:
    """Enforce max sequential high-risk tool depth per job."""
    key = _chain_key(request)
    state = _chains.setdefault(key, ToolChainState())
    if is_high_risk_tool(request.tool_name):
        limit = settings.max_high_risk_tool_chain_depth
        if state.consecutive_high_risk >= limit:
            raise ToolChainDepthExceeded(f"High-risk tool chain depth exceeded ({limit} sequential max)")
        state.consecutive_high_risk += 1
    else:
        state.consecutive_high_risk = 0


def get_chain_state(key: str) -> ToolChainState:
    return _chains.setdefault(key, ToolChainState())


def clear_chain_state(key: str) -> None:
    _chains.pop(key, None)


def clear_all_chain_states() -> None:
    _chains.clear()
