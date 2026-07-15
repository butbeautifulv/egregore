from __future__ import annotations

from cys_core.application.ports.policy_merge import PolicyMergePort
from cys_core.domain.catalog.models import ProfilePack, ProfilePolicyPayload
from cys_core.infrastructure.catalog.policy_merge import merge_profile_pack, merge_profile_policy


class PolicyMergeAdapter:
    def merge_profile_policy(self, existing: ProfilePolicyPayload, patch: dict) -> ProfilePolicyPayload:
        return merge_profile_policy(existing, patch)

    def merge_profile_pack(
        self,
        existing: ProfilePack | None,
        *,
        profile_id: str,
        body: dict,
    ) -> ProfilePack:
        return merge_profile_pack(existing, profile_id=profile_id, body=body)


def build_policy_merge_port() -> PolicyMergePort:
    return PolicyMergeAdapter()
