from __future__ import annotations

SIEM_TOOL_NAMES: frozenset[str] = frozenset(
    {
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

SIEM_TOOL_DESCRIPTIONS: dict[str, str] = {
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
