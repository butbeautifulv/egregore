from __future__ import annotations

from collections.abc import Callable

from cys_core.application.catalog_mutation_service import CatalogMutationService
from cys_core.application.ports.catalog import AgentCatalogPort
from cys_core.application.ports.policy_merge import PolicyMergePort
from cys_core.domain.catalog.models import ProfilePack


class UpsertProfilePack:
    def __init__(
        self,
        catalog: AgentCatalogPort,
        *,
        policy_merge: PolicyMergePort,
        mutation: CatalogMutationService | None = None,
        reload: Callable[[], None] | None = None,
    ) -> None:
        self._catalog = catalog
        self._policy_merge = policy_merge
        self._mutation = mutation
        self._reload = reload or (lambda: None)

    def execute(
        self,
        profile_id: str,
        body: dict,
        *,
        actor: str = "api",
    ) -> ProfilePack:
        existing = next(
            (profile for profile in self._catalog.list_profiles() if profile.id == profile_id),
            None,
        )
        profile = self._policy_merge.merge_profile_pack(existing, profile_id=profile_id, body=body)
        if self._mutation is not None:
            return self._mutation.upsert_profile(profile, actor=actor)
        saved = self._catalog.upsert_profile(profile)
        self._reload()
        return saved
