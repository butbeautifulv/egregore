from __future__ import annotations

from typing import Protocol

from cys_core.domain.catalog.models import ProfilePack, ProfilePolicyPayload


class PolicyMergePort(Protocol):
    def merge_profile_policy(self, existing: ProfilePolicyPayload, patch: dict) -> ProfilePolicyPayload: ...

    def merge_profile_pack(
        self,
        existing: ProfilePack | None,
        *,
        profile_id: str,
        body: dict,
    ) -> ProfilePack: ...
