from __future__ import annotations

from cys_core.domain.catalog.models import ProfilePolicyPayload
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID
from cys_core.domain.reasoning.sgr_models import SgrPolicy

PRODUCT_TOOL_ALLOWLIST: dict[str, frozenset[str]] = {
    "gaia-benchmark": frozenset(
        {
            "web_search",
            "read_document",
            "reasoning_check",
            "reasoning_step",
            "extract_structured_output",
            "delegate_research",
            "python_sandbox",
            "vision_analyze",
            "search_archived_webpage",
            "plan_tool_calls",
            "browser_use",
            "transcribe_audio",
            "load_skill",
            "search_personas",
            "search_skills",
            "search_tools",
            "update_todos",
            "ask_user",
        }
    ),
    "general-assistant": frozenset(
        {
            "search_personas",
            "search_skills",
            "search_tools",
            "update_todos",
            "ask_user",
            "web_search",
            "read_document",
            "reasoning_check",
            "reasoning_step",
            "extract_structured_output",
            "delegate_research",
            "load_skill",
            "plan_tool_calls",
            "create_report_outline",
        }
    ),
}

# Legacy alias used in older policy tables.
PRODUCT_TOOL_ALLOWLIST["gaia-bench"] = PRODUCT_TOOL_ALLOWLIST["gaia-benchmark"]
PRODUCT_TOOL_ALLOWLIST["general"] = PRODUCT_TOOL_ALLOWLIST["general-assistant"]


def product_tool_allowlist(profile_id: str) -> frozenset[str] | None:
    if profile_id == DEFAULT_PROFILE_ID:
        return None
    return PRODUCT_TOOL_ALLOWLIST.get(profile_id)


def profile_policy_for(profile_id: str) -> ProfilePolicyPayload:
    """Merge static platform defaults with product-specific overlays."""
    from cys_core.domain.policy.defaults import (
        ACTION_RISK_MAPPING,
        DEFAULT_MODE_POLICY,
        ESCALATION_ONLY_PATHS,
        PROFILE_TOOL_ALLOWLIST,
    )

    tool_allowlist: dict[str, list[str] | None] = {}
    for pid, allow in PROFILE_TOOL_ALLOWLIST.items():
        tool_allowlist[pid] = None if allow is None else sorted(allow)
    product_allow = product_tool_allowlist(profile_id)
    if product_allow is not None:
        tool_allowlist[profile_id] = sorted(product_allow)
    escalation_paths = [list(pair) for pair in sorted(ESCALATION_ONLY_PATHS)]
    updates: dict = {
        "tool_allowlist": tool_allowlist,
        "tool_risk": dict(ACTION_RISK_MAPPING),
        "mode_policy": DEFAULT_MODE_POLICY,
        "escalation_paths": escalation_paths,
    }
    if profile_id == DEFAULT_PROFILE_ID:
        updates["datasource_capability_grants"] = {
            DEFAULT_PROFILE_ID: {
                "siem-readonly": ["query"],
                "rag-index": ["query"],
            }
        }
    if profile_id == "general-assistant":
        updates["datasource_allowlist"] = {
            "general-assistant": ["web-cache", "docs-index"],
        }
    if profile_id in {"gaia-benchmark", "gaia-bench"}:
        updates["sgr"] = SgrPolicy(enabled=True, mode="sgr_hybrid")
        updates["datasource_allowlist"] = {
            profile_id: ["web-cache", "docs-index"],
        }
    return ProfilePolicyPayload(**updates)


def gaia_profile_policy_payload() -> ProfilePolicyPayload:
    return profile_policy_for("gaia-benchmark")
