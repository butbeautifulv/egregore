from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool

from cys_core.integrations.veil_mcp_client import VEIL_MCP_TOOL_NAMES

# Descriptions aligned with Veil knowledge MCP (read-only).
VEIL_TOOL_DESCRIPTIONS: dict[str, str] = {
    "ti_list_categories": "List Veil graph product categories (vuln, ti, mitre, playbook, …).",
    "ti_list_kinds_in_category": "List Neo4j node labels within a Veil category with counts.",
    "ti_nodes_by_category": "List graph nodes for a category + kind label.",
    "ti_search_in_category": "Search Veil knowledge graph within a category (optional kind).",
    "ti_get_node": "Fetch one Veil graph node by element id.",
    "ti_neighbors": "Fetch k-hop subgraph around a Veil graph node.",
    "ti_health": "Veil graph API and Neo4j connectivity health check.",
    "playbook_search": "Search Veil cybersecurity procedure playbooks by keywords and optional subdomain.",
    "playbook_get": "Fetch full playbook markdown for a skill id from playbook_search.",
    "playbook_procedure": "Structured procedure steps for a playbook skill id.",
    "playbook_for_technique": "List playbooks linked to a MITRE ATT&CK technique id.",
    "playbook_framework": "Read Veil MITRE Navigator layer, coverage summary, or mapping docs.",
    "playbook_subdomains": "List Anthropic skill subdomain counts from Veil playbook index.",
    "playbook_ontology_subdomains": "Veil subdomain registry with category mapping and priority tier.",
}


def make_veil_tool(name: str, description: str) -> BaseTool:
    def _run(**kwargs: Any) -> str:
        from interfaces.gateways.tool.adapters.veil_mcp import call_veil_tool

        result = call_veil_tool(name, kwargs)
        return json.dumps(result, ensure_ascii=False)

    return StructuredTool.from_function(func=_run, name=name, description=description)


def build_veil_tools() -> list[BaseTool]:
    tools: list[BaseTool] = []
    for name in sorted(VEIL_MCP_TOOL_NAMES):
        desc = VEIL_TOOL_DESCRIPTIONS.get(name, f"Veil knowledge MCP tool: {name}")
        tools.append(make_veil_tool(name, desc))
    return tools
