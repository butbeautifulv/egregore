from __future__ import annotations

from cys_core.domain.tools.models import ToolDefinitionView, ToolStatus

_SIEM_MCP_TOOLS: tuple[str, ...] = (
    "investigate_incident",
    "list_incidents",
    "get_event_by_uuid",
    "search_events",
    "list_aggregated_events",
    "lookup_assets_by_ip",
    "export_table_list",
    "search_user_actions",
    "search_api_docs",
)

SIEM_TOOL_NAMES: frozenset[str] = frozenset({"query_siem_readonly", *_SIEM_MCP_TOOLS})

_SIEM_MCP_DESCRIPTIONS: dict[str, str] = {
    "investigate_incident": "Primary SIEM triage: incident context, events, optional assets/IOC.",
    "list_incidents": "List SIEM incidents (status queue).",
    "get_event_by_uuid": "Fetch one SIEM event by UUID.",
    "search_events": "Search SIEM events by PDQL where clause.",
    "list_aggregated_events": "Aggregated SIEM events for timeline.",
    "lookup_assets_by_ip": "Resolve SIEM assets by IP.",
    "export_table_list": "Export SIEM table list / IOC data.",
    "search_user_actions": "Search SIEM user audit actions.",
    "search_api_docs": "Search local MaxPatrol SIEM API documentation.",
}

SIEM_TOOL_DEFINITIONS: list[ToolDefinitionView] = [
    ToolDefinitionView(
        name="query_siem_readonly",
        module="siem",
        status=ToolStatus.REAL,
        datasource_id="siem-readonly",
        description="Read-only SIEM search (alias → search_events when SIEM MCP enabled).",
    ),
    *[
        ToolDefinitionView(
            name=name,
            module="siem-mcp",
            status=ToolStatus.REAL,
            datasource_id="siem-mcp",
            description=_SIEM_MCP_DESCRIPTIONS[name],
        )
        for name in _SIEM_MCP_TOOLS
    ],
]
