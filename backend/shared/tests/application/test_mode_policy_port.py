from __future__ import annotations

import pytest

from cys_core.application.ports.profile_policy import ProfilePolicyPort
from cys_core.domain.catalog.models import ModePolicyPayload, ProfilePolicyPayload
from cys_core.domain.runs.mode_policy import ModePolicy
from cys_core.domain.runs.models import InteractionMode


class _FakePolicyPort(ProfilePolicyPort):
    def __init__(self, policy: ProfilePolicyPayload) -> None:
        self._policy = policy

    def get_policy(self, profile_id: str) -> ProfilePolicyPayload:
        return self._policy

    def get_trust_floor(self, profile_id: str) -> float:
        return self._policy.trust_floor

    def get_bus_policy(self, profile_id: str) -> dict[str, list[str]]:
        return self._policy.bus_policy

    def get_escalation_paths(self, profile_id: str) -> set[tuple[str, str]]:
        return set()

    def get_hitl_threshold(self, profile_id: str) -> str:
        return self._policy.hitl_auto_approve_threshold

    def get_max_spawn_depth(self, profile_id: str) -> int:
        return self._policy.max_spawn_depth

    def get_cost_per_1k_tokens(self, profile_id: str) -> float:
        return self._policy.cost_per_1k_tokens_usd

    def get_notify_control_severities(self, profile_id: str) -> set[str]:
        return set(self._policy.notify_control_severities)


@pytest.mark.unit
def test_mode_policy_injected_mode_policy_payload():
    custom = ModePolicyPayload(
        read_only_tools=["custom_read"],
        plan_blocked_tools=["spawn_worker"],
        mutating_tools=["spawn_worker"],
    )
    assert ModePolicy.allow_tool(InteractionMode.ASK, "custom_read", mode_policy=custom) is True
    assert ModePolicy.allow_tool(InteractionMode.ASK, "execute_command", mode_policy=custom) is False
    assert ModePolicy.allow_tool(InteractionMode.PLAN, "spawn_worker", mode_policy=custom) is False


@pytest.mark.unit
def test_mode_policy_from_profile_policy_port():
    port = _FakePolicyPort(
        ProfilePolicyPayload(
            mode_policy=ModePolicyPayload(
                read_only_tools=["web_search"],
                plan_blocked_tools=["spawn_worker"],
                mutating_tools=["spawn_worker"],
            )
        )
    )
    mode_policy = port.get_policy("cybersec-soc").mode_policy
    assert ModePolicy.allow_tool(InteractionMode.ASK, "web_search", mode_policy=mode_policy) is True
    assert ModePolicy.allow_tool(InteractionMode.PLAN, "spawn_worker", mode_policy=mode_policy) is False
