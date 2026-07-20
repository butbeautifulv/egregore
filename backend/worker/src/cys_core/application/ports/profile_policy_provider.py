from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cys_core.application.ports.profile_policy import ProfilePolicyPort

_profile_policy_provider: Callable[[], ProfilePolicyPort] | None = None


def configure_profile_policy_provider(fn: Callable[[], ProfilePolicyPort]) -> None:
    global _profile_policy_provider
    _profile_policy_provider = fn


def get_profile_policy_provider() -> ProfilePolicyPort:
    if _profile_policy_provider is None:
        raise RuntimeError("Profile policy provider not configured")
    return _profile_policy_provider()
