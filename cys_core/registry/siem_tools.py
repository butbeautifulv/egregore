from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel

from cys_core.application.runs.tool_coercion import normalize_siem_tool_args
from cys_core.integrations.siem_mcp_client import get_siem_allowed_tools
from cys_core.registry.siem_tool_schemas import (
    GenericSiemToolInput,
    GetEventByUuidInput,
    InvestigateIncidentInput,
    ListIncidentsInput,
    SearchEventsInput,
)

_SIEM_TOOL_DESCRIPTIONS: dict[str, str] = {
    "investigate_incident": (
        "Use FIRST when triaging a SIEM incident by ID. "
        "Required arg: incident_id (UUID string, not 'id' or 'kwargs'). "
        "Returns incident summary, correlated events, and optional asset/IOC context. "
        "Do NOT use siem_request if this tool applies."
    ),
    "list_incidents": (
        "List SIEM incidents (New/InProgress queue). "
        "Use before investigate_incident when no incident ID is known."
    ),
    "get_event_by_uuid": "Fetch one SIEM event by UUID for drill-down after investigate_incident or search_events.",
    "search_events": (
        "Search SIEM events by PDQL where clause for correlation and timeline enrichment. "
        "Use after investigate_incident when you need additional predicates."
    ),
    "list_aggregated_events": "List aggregated SIEM events for timeline visualization around an incident window.",
    "lookup_assets_by_ip": "Enrich investigation targets: resolve assets by IP from SIEM asset inventory.",
    "export_table_list": "Export tabular IOC/list data from SIEM table lists for lookup during triage.",
    "search_user_actions": "Audit who changed an incident or SIEM object (user action log).",
    "search_api_docs": "Escape hatch: search local MaxPatrol SIEM API docs when typed tools are insufficient.",
}

_SIEM_TOOL_SCHEMAS: dict[str, type[BaseModel]] = {
    "investigate_incident": InvestigateIncidentInput,
    "list_incidents": ListIncidentsInput,
    "search_events": SearchEventsInput,
    "get_event_by_uuid": GetEventByUuidInput,
}


def _invoke_siem_tool(name: str, args: dict[str, Any]) -> str:
    from cys_core.infrastructure.tools.adapters.siem_mcp import call_siem_tool

    normalized = normalize_siem_tool_args(name, args)
    result = call_siem_tool(name, normalized)
    return json.dumps(result, ensure_ascii=False)


def _make_typed_siem_tool(name: str, description: str, schema: type[BaseModel]) -> BaseTool:
    def _run(**kwargs: Any) -> str:
        return _invoke_siem_tool(name, kwargs)

    return StructuredTool.from_function(
        func=_run,
        name=name,
        description=description,
        args_schema=schema,
    )


def make_siem_tool(name: str, description: str) -> BaseTool:
    schema = _SIEM_TOOL_SCHEMAS.get(name)
    if schema is not None:
        return _make_typed_siem_tool(name, description, schema)

    def _run(**kwargs: Any) -> str:
        return _invoke_siem_tool(name, kwargs)

    return StructuredTool.from_function(
        func=_run,
        name=name,
        description=description,
        args_schema=GenericSiemToolInput,
    )


def _description_for_siem_tool(name: str, profile_id: str = "cybersec-soc") -> str:
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
    return _SIEM_TOOL_DESCRIPTIONS.get(name, f"MaxPatrol SIEM MCP tool: {name}")


def build_siem_tools(*, profile_id: str = "cybersec-soc") -> list[BaseTool]:
    tools: list[BaseTool] = []
    for name in sorted(get_siem_allowed_tools(profile_id)):
        desc = _description_for_siem_tool(name, profile_id)
        tools.append(make_siem_tool(name, desc))
    return tools
