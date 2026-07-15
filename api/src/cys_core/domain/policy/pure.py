from __future__ import annotations

from cys_core.domain.catalog.models import AgentCatalogEntry, ModePolicyPayload, ProfilePolicyPayload
from cys_core.domain.policy.defaults import (
    ACTION_RISK_MAPPING,
    DEFAULT_MODE_POLICY,
    PERSONA_CLEARANCE,
    PLAN_BLOCKED_TOOLS,
    PROFILE_TOOL_ALLOWLIST,
    READ_ONLY_TOOLS,
    MUTATING_TOOLS,
    get_persona_budgets,
)
from cys_core.domain.runs.models import InteractionMode
from cys_core.domain.workers.models import DEFAULT_BUDGET, PersonaBudget

_MUTATING_TOOL_PREFIXES = ("run_", "write_", "spawn_", "execute_")


def classify_tool_risk_pure(tool_name: str, policy: ProfilePolicyPayload | None = None):
    from cys_core.domain.security.risk_level import RiskLevel

    if policy is not None and not isinstance(policy, ProfilePolicyPayload):
        policy = None
    if policy and policy.tool_risk.get(tool_name):
        return RiskLevel(policy.tool_risk[tool_name])
    raw = ACTION_RISK_MAPPING.get(tool_name, RiskLevel.HIGH.value)
    return RiskLevel(raw)


def mode_sets_from_policy(policy: ModePolicyPayload | None = None) -> tuple[frozenset[str], frozenset[str], frozenset[str]]:
    if policy and (policy.read_only_tools or policy.plan_blocked_tools):
        read_only = frozenset(policy.read_only_tools) if policy.read_only_tools else READ_ONLY_TOOLS
        plan_blocked = frozenset(policy.plan_blocked_tools) if policy.plan_blocked_tools else PLAN_BLOCKED_TOOLS
        mutating = frozenset(policy.mutating_tools) if policy.mutating_tools else MUTATING_TOOLS
        return read_only, plan_blocked, mutating
    return READ_ONLY_TOOLS, PLAN_BLOCKED_TOOLS, MUTATING_TOOLS


def allow_tool_pure(
    mode: InteractionMode | None,
    tool_name: str,
    *,
    mode_policy: ModePolicyPayload | None = None,
) -> bool:
    if mode is None:
        return True
    read_only, plan_blocked, mutating = mode_sets_from_policy(mode_policy or DEFAULT_MODE_POLICY)
    if mode == InteractionMode.PLAN:
        return tool_name not in plan_blocked and not _is_mutating(tool_name, mutating)
    if mode == InteractionMode.ASK:
        return tool_name in read_only or tool_name.startswith("search_")
    return True


def _is_mutating(tool_name: str, mutating: frozenset[str]) -> bool:
    if tool_name in mutating:
        return True
    return any(tool_name.startswith(prefix) for prefix in _MUTATING_TOOL_PREFIXES)


def allowlist_for_profile(profile_id: str, policy: ProfilePolicyPayload | None) -> frozenset[str] | None:
    if policy and profile_id in policy.tool_allowlist:
        allowed = policy.tool_allowlist[profile_id]
        return None if allowed is None else frozenset(allowed)
    return PROFILE_TOOL_ALLOWLIST.get(profile_id)


def filter_tools_pure(
    tool_names: list[str],
    profile_id: str,
    *,
    policy: ProfilePolicyPayload | None = None,
) -> list[str]:
    allowlist = allowlist_for_profile(profile_id, policy)
    if allowlist is None:
        return list(tool_names)
    return [name for name in tool_names if name in allowlist]


def persona_budget_pure(persona: str, entry: AgentCatalogEntry | None = None) -> PersonaBudget:
    if entry is not None and (entry.budget_max_tokens is not None or entry.budget_max_cost_usd is not None):
        return PersonaBudget(
            max_tokens=entry.budget_max_tokens or DEFAULT_BUDGET.max_tokens,
            max_cost_usd=entry.budget_max_cost_usd or DEFAULT_BUDGET.max_cost_usd,
            max_tool_calls=entry.budget_max_tool_calls or DEFAULT_BUDGET.max_tool_calls,
        )
    return get_persona_budgets().get(persona, DEFAULT_BUDGET)


def persona_clearance_pure(persona: str, entry: AgentCatalogEntry | None = None):
    from cys_core.domain.security.data_classification import DataClassification

    if entry is not None and entry.data_clearance:
        return DataClassification(entry.data_clearance)
    raw = PERSONA_CLEARANCE.get(persona, DataClassification.INTERNAL.value)
    return DataClassification(raw)
