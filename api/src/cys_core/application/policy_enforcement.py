from __future__ import annotations

from cys_core.application.policy_resolver import ProfilePolicyResolver
from cys_core.domain.catalog.models import AgentCatalogEntry, ProfilePolicyPayload
from cys_core.domain.policy.pure import (
    allow_tool_pure,
    classify_tool_risk_pure,
    filter_tools_pure,
    persona_budget_pure,
    persona_clearance_pure,
)
from cys_core.domain.security.classification import DataClassification
from cys_core.domain.security.risk import RiskLevel
from cys_core.domain.runs.models import InteractionMode
from cys_core.domain.workers.budgets import PersonaBudget


class PolicyEnforcementService:
    """Application wrapper: load policy from port, delegate to pure domain."""

    def __init__(self, resolver: ProfilePolicyResolver | None = None) -> None:
        self._resolver = resolver or ProfilePolicyResolver()

    def policy(self, profile_id: str) -> ProfilePolicyPayload:
        return self._resolver.policy(profile_id)

    def classify_tool_risk(self, tool_name: str, profile_id: str) -> RiskLevel:
        return classify_tool_risk_pure(tool_name, self.policy(profile_id))

    def allow_tool(self, mode: InteractionMode | None, tool_name: str, profile_id: str) -> bool:
        policy = self.policy(profile_id)
        return allow_tool_pure(mode, tool_name, mode_policy=policy.mode_policy)

    def filter_tools(self, tool_names: list[str], profile_id: str) -> list[str]:
        return filter_tools_pure(tool_names, profile_id, policy=self.policy(profile_id))

    def persona_budget(self, persona: str, entry: AgentCatalogEntry | None = None) -> PersonaBudget:
        return persona_budget_pure(persona, entry)

    def persona_clearance(self, persona: str, entry: AgentCatalogEntry | None = None) -> DataClassification:
        return persona_clearance_pure(persona, entry)

    def trust_floor(self, profile_id: str) -> float:
        return self.policy(profile_id).trust_floor

    def max_spawn_depth(self, profile_id: str) -> int:
        return self._resolver.max_spawn_depth(profile_id)
