from __future__ import annotations

from cys_core.domain.catalog.models import ModePolicyPayload
from cys_core.domain.policy.defaults import DEFAULT_MODE_POLICY, MUTATING_TOOLS
from cys_core.domain.policy.pure import allow_tool_pure
from cys_core.domain.runs.models import InteractionMode

_SPAWN_BUS_TYPES = frozenset({"spawn_worker"})


class ModePolicy:
    """Pure domain policy for interaction modes."""

    @staticmethod
    def allow_tool(
        mode: InteractionMode | None,
        tool_name: str,
        *,
        mode_policy: ModePolicyPayload | None = None,
    ) -> bool:
        policy = mode_policy if mode_policy is not None else DEFAULT_MODE_POLICY
        return allow_tool_pure(mode, tool_name, mode_policy=policy)

    @staticmethod
    def allow_bus_message(mode: InteractionMode | None, message_type: str) -> bool:
        if mode is None:
            return True
        if mode in (InteractionMode.PLAN, InteractionMode.ASK):
            return message_type not in _SPAWN_BUS_TYPES
        return True

    @staticmethod
    def allow_spawn(mode: InteractionMode | None) -> bool:
        if mode is None:
            return True
        return mode in (InteractionMode.AGENT, InteractionMode.DEBUG)


def _is_mutating(tool_name: str, mutating: frozenset[str] | None = None) -> bool:
    tools = mutating or MUTATING_TOOLS
    if tool_name in tools:
        return True
    prefixes = ("run_", "write_", "spawn_", "execute_")
    return any(tool_name.startswith(prefix) for prefix in prefixes)
