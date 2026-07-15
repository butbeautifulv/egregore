from __future__ import annotations

from typing import TYPE_CHECKING

from cys_core.application.policy_enforcement import PolicyEnforcementService
from cys_core.application.policy_resolver import (
    ProfilePolicyResolver,
    configure_policy_resolver_from_settings,
)
from cys_core.infrastructure.catalog.catalog_registry import get_agent_catalog
from cys_core.infrastructure.catalog.profile_policy import ProfilePolicyLoader

if TYPE_CHECKING:
    from bootstrap.settings import Settings


class PolicyContainer:
    """Owns profile-policy loading/resolution/enforcement wiring.

    Extracted verbatim from ``Container.__init__`` — this construction runs
    eagerly (not lazily) so it must be built first, same as before the
    god-object split, since ``PolicyEnforcementService`` and downstream
    getters assume it already exists.
    """

    def __init__(self, settings: "Settings") -> None:
        from cys_core.infrastructure.observability.metrics_adapter import build_metrics_port

        self._policy_loader = ProfilePolicyLoader(get_agent_catalog)
        self._resolver = configure_policy_resolver_from_settings(
            settings,
            policy_loader=self._policy_loader,
            metrics_port=build_metrics_port(),
        )
        self._enforcement = PolicyEnforcementService(self._resolver)

    def get_profile_policy_port(self) -> ProfilePolicyLoader:
        return self._policy_loader

    def get_policy_resolver(self) -> ProfilePolicyResolver:
        return self._resolver

    def get_policy_enforcement(self) -> PolicyEnforcementService:
        return self._enforcement
