from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel

from cys_core.integrations.nessus_mcp_client import get_nessus_allowed_tools
from cys_core.registry.nessus_tool_schemas import (
    CreateScanInput,
    GenericNessusToolInput,
    GetAssetFindingsInput,
    LaunchScanInput,
    LookupAssetByIpInput,
    SearchInventoryInput,
    SyncScanInventoryInput,
    WaitForScanInput,
)

_NESSUS_TOOL_DESCRIPTIONS: dict[str, str] = {
    "list_scans": "List Nessus scan configurations. Use first to pick scan_id for inventory sync.",
    "list_scan_templates": "List Nessus scan templates to pick template_uuid for create_scan.",
    "create_scan": "Create a new Nessus scan (name, text_targets, optional template_name).",
    "launch_scan": "Launch an existing Nessus scan by scan_id.",
    "get_scan_status": "Get Nessus scan status (running/completed/etc.).",
    "wait_for_scan": "Poll Nessus scan until completed or timeout before syncing inventory.",
    "sync_scan_inventory": (
        "Export Nessus scan results into local security inventory (CMDB). "
        "Use after scan completes; avoids repeat export when snapshot is fresh."
    ),
    "lookup_asset_by_ip": "Lookup host vulnerability inventory by IP from synced Nessus data.",
    "search_inventory": "Search local Nessus inventory by IP fragment, OS, or severity counts.",
    "get_asset_vuln_summary": "Aggregated Critical/High/Medium/Low counts for one asset.",
    "get_asset_findings": "List plugin-level findings for an asset from local inventory.",
    "list_high_risk_assets": "List assets with critical or high findings from local inventory.",
    "search_api_docs": "Search local Nessus API reference when typed tools are insufficient.",
}

_NESSUS_TOOL_SCHEMAS: dict[str, type[BaseModel]] = {
    "create_scan": CreateScanInput,
    "launch_scan": LaunchScanInput,
    "sync_scan_inventory": SyncScanInventoryInput,
    "wait_for_scan": WaitForScanInput,
    "lookup_asset_by_ip": LookupAssetByIpInput,
    "get_asset_findings": GetAssetFindingsInput,
    "search_inventory": SearchInventoryInput,
}


def _invoke_nessus_tool(name: str, args: dict[str, Any]) -> str:
    from cys_core.infrastructure.tools.adapters.nessus_mcp import call_nessus_tool

    result = call_nessus_tool(name, args)
    return json.dumps(result, ensure_ascii=False)


def make_nessus_tool(name: str, description: str) -> BaseTool:
    schema = _NESSUS_TOOL_SCHEMAS.get(name, GenericNessusToolInput)

    def _run(**kwargs: Any) -> str:
        return _invoke_nessus_tool(name, kwargs)

    return StructuredTool.from_function(
        func=_run,
        name=name,
        description=description,
        args_schema=schema,
    )


def _description_for_nessus_tool(name: str, profile_id: str = "cybersec-hunter") -> str:
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
    return _NESSUS_TOOL_DESCRIPTIONS.get(name, f"Nessus MCP tool: {name}")


def build_nessus_tools(*, profile_id: str = "cybersec-hunter") -> list[BaseTool]:
    tools: list[BaseTool] = []
    for name in sorted(get_nessus_allowed_tools(profile_id)):
        desc = _description_for_nessus_tool(name, profile_id)
        tools.append(make_nessus_tool(name, desc))
    return tools
