from __future__ import annotations

SIEM_TOOLS = frozenset(
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
    }
)

VEIL_TOOLS = frozenset(
    {
        "ti_list_categories",
        "ti_list_kinds_in_category",
        "ti_nodes_by_category",
        "ti_search_in_category",
        "ti_get_node",
        "ti_neighbors",
        "ti_health",
        "playbook_search",
        "playbook_get",
        "playbook_procedure",
        "playbook_for_technique",
        "playbook_framework",
        "playbook_subdomains",
        "playbook_ontology_subdomains",
    }
)

NESSUS_TOOLS = frozenset(
    {
        "list_scans",
        "list_scan_templates",
        "create_scan",
        "launch_scan",
        "get_scan_status",
        "wait_for_scan",
        "sync_scan_inventory",
        "lookup_asset_by_ip",
        "search_inventory",
        "get_asset_vuln_summary",
        "get_asset_findings",
        "list_high_risk_assets",
        "search_api_docs",
    }
)

TOOL_TO_DATASOURCE: dict[str, str] = {
    **{tool: "siem-readonly" for tool in SIEM_TOOLS},
    **{tool: "veil-knowledge" for tool in VEIL_TOOLS},
    **{tool: "nessus" for tool in NESSUS_TOOLS},
}


def datasource_object(datasource_id: str) -> str:
    return f"datasource:{datasource_id}"


def datasource_seed_tuples(
    organization_id: str,
    *,
    datasource_ids: list[str] | None = None,
) -> list[tuple[str, str, str]]:
    """FGA tuple triples for datasource ownership by organization."""
    org = (organization_id or "default").strip() or "default"
    ids = datasource_ids or sorted(set(TOOL_TO_DATASOURCE.values()))
    return [(f"organization:{org}", "organization", datasource_object(datasource_id)) for datasource_id in ids]


def workspace_datasource_consumer_tuples(
    workspace_id: str,
    datasource_ids: list[str],
) -> list[tuple[str, str, str]]:
    """FGA tuple triples granting a workspace datasource query access."""
    workspace = workspace_id.strip()
    return [
        (f"workspace:{workspace}", "consumer", datasource_object(datasource_id))
        for datasource_id in datasource_ids
    ]
