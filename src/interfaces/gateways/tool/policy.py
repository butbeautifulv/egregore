from __future__ import annotations

from cys_core.application.tools.tool_chain_policy import ToolChainPolicy, ToolChainState
from cys_core.domain.tools.exceptions import ToolChainDepthExceeded
from interfaces.gateways.tool.models import ToolInvokeRequest

__all__ = [
    "ToolChainDepthExceeded",
    "ToolChainState",
    "ToolChainPolicy",
    "check_tool_chain",
    "clear_all_chain_states",
    "clear_chain_state",
    "get_chain_state",
    "is_high_risk_tool",
]


def _policy() -> ToolChainPolicy:
    from bootstrap.container import get_container

    return get_container().get_tool_chain_policy()


def is_high_risk_tool(tool_name: str) -> bool:
    return ToolChainPolicy.is_high_risk_tool(tool_name)


def check_tool_chain(request: ToolInvokeRequest) -> None:
    from interfaces.gateways.tool.mappers import to_command

    _policy().check(to_command(request))


def get_chain_state(key: str) -> ToolChainState:
    return _policy().get_chain_state(key)


def clear_chain_state(key: str) -> None:
    _policy().clear(key)


def clear_all_chain_states() -> None:
    _policy().clear_all()
