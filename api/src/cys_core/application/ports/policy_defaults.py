from __future__ import annotations

from typing import Protocol

from cys_core.domain.catalog.models import ProfilePolicyPayload


class PolicyDefaultsPort(Protocol):
    def default_profile_policy(self) -> ProfilePolicyPayload: ...
