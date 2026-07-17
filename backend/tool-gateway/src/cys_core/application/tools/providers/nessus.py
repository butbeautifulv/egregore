from __future__ import annotations

from cys_core.domain.tools.models import ToolDefinitionView, ToolStatus

_NESSUS_MCP_TOOLS: tuple[str, ...] = (
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
)

NESSUS_TOOL_NAMES: frozenset[str] = frozenset(_NESSUS_MCP_TOOLS)

_NESSUS_MCP_DESCRIPTIONS: dict[str, str] = {
    "list_scans": "List Nessus scans for vulnerability inventory workflows.",
    "list_scan_templates": "List Nessus scan templates (policy UUIDs for create_scan).",
    "create_scan": "Create a new Nessus scan with name and text_targets.",
    "launch_scan": "Launch an existing Nessus scan by scan_id.",
    "get_scan_status": "Check Nessus scan completion status.",
    "wait_for_scan": "Wait until Nessus scan reaches terminal status.",
    "sync_scan_inventory": "Sync Nessus scan export into local security inventory.",
    "lookup_asset_by_ip": "Lookup synced Nessus asset by IP.",
    "search_inventory": "Search Nessus inventory by filters.",
    "get_asset_vuln_summary": "Vulnerability count summary for one asset.",
    "get_asset_findings": "Plugin findings for one asset from inventory.",
    "list_high_risk_assets": "Assets with critical/high vulnerability counts.",
    "search_api_docs": "Search local Nessus API documentation.",
}

NESSUS_TOOL_DEFINITIONS: list[ToolDefinitionView] = [
    ToolDefinitionView(
        name=name,
        module="nessus-mcp",
        status=ToolStatus.REAL,
        datasource_id="nessus-mcp",
        description=_NESSUS_MCP_DESCRIPTIONS[name],
    )
    for name in _NESSUS_MCP_TOOLS
]
