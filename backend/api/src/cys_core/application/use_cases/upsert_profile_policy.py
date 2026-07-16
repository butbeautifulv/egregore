from __future__ import annotations

from collections.abc import Callable

from cys_core.application.catalog_mutation_service import CatalogMutationService
from cys_core.application.ports.catalog import AgentCatalogPort
from cys_core.application.ports.policy_defaults import PolicyDefaultsPort
from cys_core.application.ports.policy_merge import PolicyMergePort
from cys_core.domain.catalog.models import ProfilePack, ProfilePolicyPayload


class UpsertProfilePolicy:
    def __init__(
        self,
        catalog: AgentCatalogPort,
        *,
        policy_merge: PolicyMergePort,
        policy_defaults: PolicyDefaultsPort,
        mutation: CatalogMutationService | None = None,
        reload: Callable[[], None] | None = None,
    ) -> None:
        self._catalog = catalog
        self._policy_merge = policy_merge
        self._policy_defaults = policy_defaults
        self._mutation = mutation
        self._reload = reload or (lambda: None)

    def execute(
        self,
        profile_id: str,
        policy_patch: dict,
        *,
        actor: str = "api",
    ) -> ProfilePolicyPayload:
        existing = next(
            (profile for profile in self._catalog.list_profiles() if profile.id == profile_id),
            None,
        )
        if existing is None:
            existing = ProfilePack(id=profile_id, name=profile_id)
        merged = self._policy_merge.merge_profile_policy(existing.policy, policy_patch)
        existing.policy = merged
        if self._mutation is not None:
            self._mutation.upsert_profile(existing, actor=actor)
        else:
            self._catalog.upsert_profile(existing)
            self._reload()
        return merged

    def apply_seed_defaults(self, profile_id: str, *, actor: str = "cli") -> ProfilePolicyPayload:
        existing = next(
            (profile for profile in self._catalog.list_profiles() if profile.id == profile_id),
            None,
        )
        if existing is None:
            existing = ProfilePack(id=profile_id, name=profile_id)
        merged = self._policy_merge.merge_profile_policy(
            existing.policy, self._policy_defaults.default_profile_policy().model_dump()
        )
        existing.policy = merged
        if self._mutation is not None:
            self._mutation.upsert_profile(existing, actor=actor)
        else:
            self._catalog.upsert_profile(existing)
            self._reload()
        return merged
