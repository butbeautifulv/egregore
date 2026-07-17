from __future__ import annotations

from dataclasses import dataclass

from cys_core.domain.security.risk import RiskLevel, classify_tool_risk
from cys_core.domain.tools.exceptions import ToolChainDepthExceeded
from cys_core.domain.tools.models import ToolInvokeCommand


@dataclass
class ToolChainState:
    consecutive_high_risk: int = 0


class ToolChainPolicy:
    """Enforce max sequential high-risk tool depth per job."""

    def __init__(self, *, max_high_risk_depth: int = 3) -> None:
        self._max_high_risk_depth = max_high_risk_depth
        self._chains: dict[str, ToolChainState] = {}

    @staticmethod
    def _chain_key(command: ToolInvokeCommand) -> str:
        return command.job_id or command.sandbox_id

    @staticmethod
    def is_high_risk_tool(tool_name: str) -> bool:
        return classify_tool_risk(tool_name) >= RiskLevel.HIGH

    def check(self, command: ToolInvokeCommand) -> None:
        key = self._chain_key(command)
        state = self._chains.setdefault(key, ToolChainState())
        if self.is_high_risk_tool(command.tool_name):
            limit = self._max_high_risk_depth
            if state.consecutive_high_risk >= limit:
                raise ToolChainDepthExceeded(f"High-risk tool chain depth exceeded ({limit} sequential max)")
            state.consecutive_high_risk += 1
        else:
            state.consecutive_high_risk = 0

    def get_chain_state(self, key: str) -> ToolChainState:
        return self._chains.setdefault(key, ToolChainState())

    def clear(self, key: str) -> None:
        self._chains.pop(key, None)

    def clear_all(self) -> None:
        self._chains.clear()
