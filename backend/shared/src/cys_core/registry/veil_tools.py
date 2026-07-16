from __future__ import annotations

import json
from typing import Any

import structlog
from langchain_core.tools import BaseTool, StructuredTool

from cys_core.application.workers.tool_result_cache import get_cached, normalize_playbook_query, set_cached
from cys_core.integrations.veil_mcp_client import get_veil_allowed_tools

logger = structlog.get_logger(__name__)

_TRUNCATE_LIMITS: dict[str, int] = {
    "playbook_procedure": 4_000,
    "playbook_get": 3_000,
}

_VEIL_TOOL_DESCRIPTIONS: dict[str, str] = {
    "ti_list_categories": "List Veil graph product categories (vuln, ti, mitre, playbook, …).",
    "ti_list_kinds_in_category": "List Neo4j node labels within a Veil category with counts.",
    "ti_nodes_by_category": "List graph nodes for a category + kind label.",
    "ti_search_in_category": (
        "Search Veil graph within a category (ti, vuln, mitre, …). "
        "Required: category + query. Call ti_list_categories first if unsure. "
        "Use category=ti for IOC/IP/domain enrichment."
    ),
    "ti_get_node": "Fetch one Veil graph node by element id after ti_search_in_category.",
    "ti_neighbors": "Fetch k-hop subgraph around a Veil graph node for relationship context.",
    "ti_health": "Veil graph API and Neo4j connectivity health check.",
    "playbook_search": (
        "Use FIRST when you need a cybersecurity procedure playbook by keywords and optional subdomain."
    ),
    "playbook_get": "Fetch full playbook markdown for a skill id from playbook_search.",
    "playbook_procedure": "Structured procedure steps for a playbook skill id.",
    "playbook_for_technique": "Use when MITRE ATT&CK technique ID is known — list playbooks linked to it.",
    "playbook_framework": "Read Veil MITRE Navigator layer, coverage summary, or mapping docs.",
    "playbook_subdomains": "List Anthropic skill subdomain counts from Veil playbook index.",
    "playbook_ontology_subdomains": "Veil subdomain registry with category mapping and priority tier.",
}


def _job_id() -> str:
    job_id = structlog.contextvars.get_contextvars().get("job_id")
    return job_id if isinstance(job_id, str) else ""


def _truncate_tool_json(tool_name: str, payload: str) -> str:
    limit = _TRUNCATE_LIMITS.get(tool_name)
    if not limit or len(payload) <= limit:
        return payload
    return payload[:limit] + "… [truncated]"


def make_veil_tool(name: str, description: str) -> BaseTool:
    def _invoke(**kwargs: Any) -> str:
        from cys_core.infrastructure.tools.adapters.veil_mcp import call_veil_tool

        job_id = _job_id()
        if name == "ti_list_categories" and job_id:
            cached = get_cached(job_id, "ti_list_categories")
            if cached:
                return cached
        if name == "playbook_search" and job_id:
            query = kwargs.get("query", "")
            if isinstance(query, str) and query.strip():
                cache_key = f"playbook_search:{normalize_playbook_query(query)}"
                cached = get_cached(job_id, cache_key)
                if cached:
                    return cached

        result = call_veil_tool(name, kwargs)
        payload = _truncate_tool_json(name, json.dumps(result, ensure_ascii=False))

        if name == "ti_list_categories" and job_id:
            set_cached(job_id, "ti_list_categories", payload)
        elif name == "playbook_search" and job_id:
            query = kwargs.get("query", "")
            if isinstance(query, str) and query.strip():
                set_cached(job_id, f"playbook_search:{normalize_playbook_query(query)}", payload)
        return payload

    async def _ainvoke(**kwargs: Any) -> str:
        from cys_core.infrastructure.tools.adapters.veil_mcp import acall_veil_tool

        job_id = _job_id()
        if name == "ti_list_categories" and job_id:
            cached = get_cached(job_id, "ti_list_categories")
            if cached:
                return cached
        if name == "playbook_search" and job_id:
            query = kwargs.get("query", "")
            if isinstance(query, str) and query.strip():
                cache_key = f"playbook_search:{normalize_playbook_query(query)}"
                cached = get_cached(job_id, cache_key)
                if cached:
                    return cached

        result = await acall_veil_tool(name, kwargs)
        payload = _truncate_tool_json(name, json.dumps(result, ensure_ascii=False))

        if name == "ti_list_categories" and job_id:
            set_cached(job_id, "ti_list_categories", payload)
        elif name == "playbook_search" and job_id:
            query = kwargs.get("query", "")
            if isinstance(query, str) and query.strip():
                set_cached(job_id, f"playbook_search:{normalize_playbook_query(query)}", payload)
        return payload

    return StructuredTool.from_function(func=_invoke, coroutine=_ainvoke, name=name, description=description)


def _description_for_veil_tool(name: str, profile_id: str = "cybersec-soc") -> str:
    try:
        from cys_core.application.runtime_config import get_use_dynamic_catalog

        if not get_use_dynamic_catalog():
            raise RuntimeError("catalog not configured")
        from cys_core.infrastructure.catalog.registry_factory import get_tool_catalog

        entry = get_tool_catalog().get_tool(name, profile_id=profile_id)
        if entry and entry.description:
            return entry.description
    except Exception:
        pass
    return _VEIL_TOOL_DESCRIPTIONS.get(name, f"Veil knowledge MCP tool: {name}")


def build_veil_tools(*, profile_id: str = "cybersec-soc") -> list[BaseTool]:
    tools: list[BaseTool] = []
    for name in sorted(get_veil_allowed_tools(profile_id)):
        desc = _description_for_veil_tool(name, profile_id)
        tools.append(make_veil_tool(name, desc))
    return tools
