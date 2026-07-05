from __future__ import annotations

from typing import Callable

from cys_core.domain.catalog.models import ProfilePolicyPayload
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID
from cys_core.domain.policy.defaults import DEFAULT_BUS_POLICY, ESCALATION_ONLY_PATHS, default_profile_policy_payload

_DEFAULT_POLICY = default_profile_policy_payload()


class ProfilePolicyLoader:
    """Implements ProfilePolicyPort — loads policy from agent catalog."""

    def __init__(self, catalog_getter: Callable[[], object]) -> None:
        self._catalog_getter = catalog_getter

    def get_policy(self, profile_id: str = DEFAULT_PROFILE_ID) -> ProfilePolicyPayload:
        catalog = self._catalog_getter()
        for profile in catalog.list_profiles():
            if profile.id == profile_id:
                return profile.policy or _DEFAULT_POLICY
        return _DEFAULT_POLICY

    def get_trust_floor(self, profile_id: str = DEFAULT_PROFILE_ID) -> float:
        return self.get_policy(profile_id).trust_floor

    def get_bus_policy(self, profile_id: str = DEFAULT_PROFILE_ID) -> dict[str, list[str]]:
        policy = self.get_policy(profile_id).bus_policy
        if policy:
            return policy
        return dict(DEFAULT_BUS_POLICY)

    def get_breaker_config(self, profile_id: str = DEFAULT_PROFILE_ID) -> tuple[int, int]:
        policy = self.get_policy(profile_id)
        return policy.breaker_failure_threshold, policy.breaker_reset_seconds

    def get_escalation_paths(self, profile_id: str = DEFAULT_PROFILE_ID) -> set[tuple[str, str]]:
        policy = self.get_policy(profile_id)
        if policy.escalation_paths:
            return {tuple(pair) for pair in policy.escalation_paths if len(pair) == 2}
        return set(ESCALATION_ONLY_PATHS)

    def get_hitl_threshold(self, profile_id: str = DEFAULT_PROFILE_ID) -> str:
        return self.get_policy(profile_id).hitl_auto_approve_threshold

    def get_max_spawn_depth(self, profile_id: str = DEFAULT_PROFILE_ID) -> int:
        return self.get_policy(profile_id).max_spawn_depth

    def get_cost_per_1k_tokens(self, profile_id: str = DEFAULT_PROFILE_ID) -> float:
        return self.get_policy(profile_id).cost_per_1k_tokens_usd

    def get_notify_control_severities(self, profile_id: str = DEFAULT_PROFILE_ID) -> set[str]:
        return set(self.get_policy(profile_id).notify_control_severities)

    def get_default_personas(self, profile_id: str = DEFAULT_PROFILE_ID) -> list[str] | None:
        catalog = self._catalog_getter()
        for profile in catalog.list_profiles():
            if profile.id == profile_id and profile.default_personas:
                return list(profile.default_personas)
        return None


def _loader() -> ProfilePolicyLoader:
    from cys_core.infrastructure.catalog.catalog_registry import get_agent_catalog

    return ProfilePolicyLoader(get_agent_catalog)


def get_profile_policy(profile_id: str = DEFAULT_PROFILE_ID) -> ProfilePolicyPayload:
    return _loader().get_policy(profile_id)


def get_trust_floor(profile_id: str = DEFAULT_PROFILE_ID) -> float:
    return _loader().get_trust_floor(profile_id)


def get_bus_policy(profile_id: str = DEFAULT_PROFILE_ID) -> dict[str, list[str]]:
    return _loader().get_bus_policy(profile_id)


def get_breaker_config(profile_id: str = DEFAULT_PROFILE_ID) -> tuple[int, int]:
    return _loader().get_breaker_config(profile_id)


def get_escalation_paths(profile_id: str = DEFAULT_PROFILE_ID) -> set[tuple[str, str]]:
    return _loader().get_escalation_paths(profile_id)


def get_hitl_threshold(profile_id: str = DEFAULT_PROFILE_ID) -> str:
    return _loader().get_hitl_threshold(profile_id)


def get_max_spawn_depth(profile_id: str = DEFAULT_PROFILE_ID) -> int:
    return _loader().get_max_spawn_depth(profile_id)


def get_cost_per_1k_tokens(profile_id: str = DEFAULT_PROFILE_ID) -> float:
    return _loader().get_cost_per_1k_tokens(profile_id)


def get_notify_control_severities(profile_id: str = DEFAULT_PROFILE_ID) -> set[str]:
    return _loader().get_notify_control_severities(profile_id)
