from __future__ import annotations

from cys_core.domain.catalog.models import ModePolicyPayload, ProfilePolicyPayload
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID
from cys_core.domain.workers.models import PersonaBudget

DEFAULT_BUS_POLICY: dict[str, list[str]] = {
    "critic": ["control"],
    "worker": ["critic", "control"],
}

ESCALATION_ONLY_PATHS: set[tuple[str, str]] = {
    ("soc", "redteam"),
    ("network", "redteam"),
    ("intel", "redteam"),
    ("hunter", "redteam"),
}

MUTATING_TOOLS = frozenset({"spawn_worker", "update_todos"})

READ_ONLY_TOOLS = frozenset(
    {
        "query_siem_readonly",
        "investigate_incident",
        "list_incidents",
        "get_event_by_uuid",
        "search_events",
        "list_aggregated_events",
        "lookup_assets_by_ip",
        "export_table_list",
        "search_user_actions",
        "search_api_docs",
        "rag_query",
        "playbook_search",
        "playbook_get",
        "playbook_for_technique",
        "playbook_procedure",
        "playbook_framework",
        "playbook_subdomains",
        "playbook_ontology_subdomains",
        "ti_list_categories",
        "ti_list_kinds_in_category",
        "ti_nodes_by_category",
        "ti_search_in_category",
        "ti_get_node",
        "ti_neighbors",
        "ti_health",
        "search_personas",
        "search_skills",
        "search_tools",
        "read_repo_metadata",
        "parse_sast_report",
        "parse_netflow",
        "enrich_ioc",
        "correlate_dns",
        "dedup_alerts",
        "build_timeline",
        "correlate_findings",
        "load_skill",
        "web_search",
        "read_document",
        "reasoning_check",
        "reasoning_step",
        "vision_analyze",
        "search_archived_webpage",
    }
)

PLAN_BLOCKED_TOOLS = MUTATING_TOOLS | frozenset(
    {
        "ask_user",
        "delegate_research",
        "python_sandbox",
        "browser_use",
        "plan_tool_calls",
    }
)

DEFAULT_MODE_POLICY = ModePolicyPayload(
    read_only_tools=sorted(READ_ONLY_TOOLS),
    plan_blocked_tools=sorted(PLAN_BLOCKED_TOOLS),
    mutating_tools=sorted(MUTATING_TOOLS),
)

ACTION_RISK_MAPPING: dict[str, str] = {
    "parse_netflow": "low",
    "enrich_ioc": "low",
    "correlate_dns": "low",
    "query_siem_readonly": "low",
    "investigate_incident": "low",
    "list_incidents": "low",
    "get_event_by_uuid": "low",
    "search_events": "low",
    "list_aggregated_events": "low",
    "lookup_assets_by_ip": "low",
    "export_table_list": "low",
    "search_user_actions": "low",
    "search_api_docs": "low",
    "rag_query": "low",
    "dedup_alerts": "low",
    "build_timeline": "low",
    "correlate_findings": "low",
    "playbook_search": "low",
    "playbook_get": "low",
    "playbook_for_technique": "low",
    "playbook_procedure": "low",
    "playbook_framework": "low",
    "playbook_subdomains": "low",
    "playbook_ontology_subdomains": "low",
    "ti_list_categories": "low",
    "ti_list_kinds_in_category": "low",
    "ti_nodes_by_category": "low",
    "ti_search_in_category": "low",
    "ti_get_node": "low",
    "ti_neighbors": "low",
    "ti_health": "low",
    "check_control": "low",
    "map_framework": "low",
    "audit_evidence": "low",
    "read_repo_metadata": "low",
    "parse_sast_report": "low",
    "web_search": "low",
    "read_document": "low",
    "search_archived_webpage": "low",
    "vision_analyze": "medium",
    "reasoning_check": "low",
    "reasoning_step": "low",
    "extract_structured_output": "low",
    "search_personas": "low",
    "search_skills": "low",
    "search_tools": "low",
    "ask_user": "low",
    "load_skill": "low",
    "update_todos": "medium",
    "delegate_research": "medium",
    "spawn_worker": "high",
    "plan_tool_calls": "medium",
    "create_report_outline": "low",
    "transcribe_audio": "medium",
    "analyze_workflow": "medium",
    "python_sandbox": "high",
    "browser_use": "high",
    "write_file": "medium",
    "run_active_scan": "high",
    "execute_command": "critical",
    "send_email": "high",
    "database_delete": "critical",
    "transfer_funds": "critical",
}

PROFILE_TOOL_ALLOWLIST: dict[str, frozenset[str] | None] = {
    DEFAULT_PROFILE_ID: None,
}


def default_profile_policy_payload() -> ProfilePolicyPayload:
    from cys_core.domain.policy.product_payloads import profile_policy_for

    return profile_policy_for(DEFAULT_PROFILE_ID)


def gaia_profile_policy_payload() -> ProfilePolicyPayload:
    from cys_core.domain.policy.product_payloads import gaia_profile_policy_payload as _gaia

    return _gaia()


_BASE_PERSONA_BUDGETS: dict[str, PersonaBudget] = {
    "soc": PersonaBudget(max_tokens=40_000, max_cost_usd=2.0, max_tool_calls=6),
    "network": PersonaBudget(max_tokens=50_000, max_cost_usd=2.0),
    "compliance": PersonaBudget(max_tokens=40_000, max_cost_usd=1.5),
    "redteam": PersonaBudget(max_tokens=80_000, max_cost_usd=5.0),
    "intel": PersonaBudget(max_tokens=40_000, max_cost_usd=2.0, max_tool_calls=6),
    "hunter": PersonaBudget(max_tokens=55_000, max_cost_usd=2.5),
    "identity": PersonaBudget(max_tokens=50_000, max_cost_usd=2.0),
    "dfir": PersonaBudget(max_tokens=60_000, max_cost_usd=3.0),
    "cloud": PersonaBudget(max_tokens=50_000, max_cost_usd=2.0),
    "purple": PersonaBudget(max_tokens=45_000, max_cost_usd=1.5),
    "consultant": PersonaBudget(max_tokens=35_000, max_cost_usd=1.0),
    "conductor": PersonaBudget(max_tokens=60_000, max_cost_usd=3.0),
    "gaia_solver": PersonaBudget(max_tokens=80_000, max_cost_usd=4.0),
    "research": PersonaBudget(max_tokens=55_000, max_cost_usd=2.5),
    "coding": PersonaBudget(max_tokens=70_000, max_cost_usd=3.5),
}

PERSONA_BUDGETS = _BASE_PERSONA_BUDGETS
_loaded_persona_budgets: dict[str, PersonaBudget] | None = None


def configure_persona_budgets(budgets: dict[str, PersonaBudget]) -> None:
    global _loaded_persona_budgets
    _loaded_persona_budgets = dict(budgets)


def get_persona_budgets() -> dict[str, PersonaBudget]:
    if _loaded_persona_budgets is not None:
        return dict(_loaded_persona_budgets)
    return dict(_BASE_PERSONA_BUDGETS)

PERSONA_CLEARANCE: dict[str, str] = {
    "soc": "confidential",
    "network": "confidential",
    "compliance": "restricted",
    "redteam": "confidential",
    "intel": "confidential",
    "hunter": "confidential",
    "identity": "confidential",
    "dfir": "restricted",
    "cloud": "confidential",
    "purple": "internal",
    "consultant": "internal",
    "coordinator": "restricted",
    "critic": "internal",
}

