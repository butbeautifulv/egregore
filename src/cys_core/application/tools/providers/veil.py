from __future__ import annotations

from cys_core.domain.tools.models import ToolDefinitionView, ToolStatus
from cys_core.integrations.veil_mcp_client import FALLBACK_VEIL_TOOL_NAMES

_VEIL_DESCRIPTIONS: dict[str, str] = {
    "ti_list_categories": "List Veil graph product categories (vuln, ti, mitre, playbook, …).",
    "ti_list_kinds_in_category": "List Neo4j node labels within a Veil category with counts.",
    "ti_nodes_by_category": "List graph nodes for a category + kind label.",
    "ti_search_in_category": "Use FIRST for IOC/CVE/actor lookup in Veil knowledge graph.",
    "ti_get_node": "Fetch one Veil graph node by element id after ti_search_in_category.",
    "ti_neighbors": "Fetch k-hop subgraph around a Veil graph node for relationship context.",
    "ti_health": "Veil graph API and Neo4j connectivity health check.",
    "playbook_search": "Use FIRST when you need a cybersecurity procedure playbook by keywords.",
    "playbook_get": "Fetch full playbook markdown for a skill id from playbook_search.",
    "playbook_procedure": "Structured procedure steps for a playbook skill id.",
    "playbook_for_technique": "Use when MITRE ATT&CK technique ID is known — list linked playbooks.",
    "playbook_framework": "Read Veil MITRE Navigator layer, coverage summary, or mapping docs.",
    "playbook_subdomains": "List Anthropic skill subdomain counts from Veil playbook index.",
    "playbook_ontology_subdomains": "Veil subdomain registry with category mapping and priority tier.",
}

VEIL_TOOL_NAMES: frozenset[str] = FALLBACK_VEIL_TOOL_NAMES

VEIL_TOOL_DEFINITIONS: list[ToolDefinitionView] = [
    ToolDefinitionView(
        name=name,
        module="veil-mcp",
        status=ToolStatus.REAL,
        datasource_id="veil-mcp",
        description=_VEIL_DESCRIPTIONS[name],
    )
    for name in sorted(FALLBACK_VEIL_TOOL_NAMES)
]
