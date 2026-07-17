from __future__ import annotations

from typing import Any, Callable

from cys_core.infrastructure.tools.adapters.catalog_search import search_personas, search_skills, search_tools
from cys_core.infrastructure.tools.adapters.multimodal import python_sandbox, search_archived_webpage, vision_analyze
from cys_core.infrastructure.tools.adapters.nessus_mcp import call_nessus_tool, is_nessus_tool
from cys_core.infrastructure.tools.adapters.rag import rag_query_tool
from cys_core.infrastructure.tools.adapters.read_document import read_document
from cys_core.infrastructure.tools.adapters.siem import query_siem_readonly_search
from cys_core.infrastructure.tools.adapters.siem_mcp import call_siem_tool, is_siem_tool
from cys_core.infrastructure.tools.adapters.soc_stubs import (
    analyze_workflow,
    audit_evidence,
    browser_use,
    build_timeline,
    check_control,
    correlate_dns,
    correlate_findings,
    create_report_outline,
    dedup_alerts,
    enrich_ioc,
    execute_command,
    map_framework,
    parse_netflow,
    parse_sast_report,
    plan_tool_calls,
    read_repo_metadata,
    run_active_scan,
    transcribe_audio,
)
from cys_core.infrastructure.tools.adapters.veil_mcp import call_veil_tool, is_veil_tool
from cys_core.infrastructure.tools.adapters.web_search import web_search

AdapterFn = Callable[[dict[str, Any]], dict[str, Any]]

ADAPTERS: dict[str, AdapterFn] = {
    "query_siem_readonly": lambda args: query_siem_readonly_search(**args),
    "rag_query": lambda args: rag_query_tool(**args),
    "web_search": lambda args: web_search(**args),
    "read_document": lambda args: read_document(**args),
    "python_sandbox": lambda args: python_sandbox(**args),
    "vision_analyze": lambda args: vision_analyze(**args),
    "search_archived_webpage": lambda args: search_archived_webpage(**args),
    "search_personas": lambda args: search_personas(**args),
    "search_skills": lambda args: search_skills(**args),
    "search_tools": lambda args: search_tools(**args),
    "read_repo_metadata": lambda args: read_repo_metadata(**args),
    "parse_sast_report": lambda args: parse_sast_report(**args),
    "analyze_workflow": lambda args: analyze_workflow(**args),
    "run_active_scan": lambda args: run_active_scan(**args),
    "parse_netflow": lambda args: parse_netflow(**args),
    "enrich_ioc": lambda args: enrich_ioc(**args),
    "correlate_dns": lambda args: correlate_dns(**args),
    "dedup_alerts": lambda args: dedup_alerts(**args),
    "build_timeline": lambda args: build_timeline(**args),
    "correlate_findings": lambda args: correlate_findings(**args),
    "check_control": lambda args: check_control(**args),
    "map_framework": lambda args: map_framework(**args),
    "audit_evidence": lambda args: audit_evidence(**args),
    "execute_command": lambda args: execute_command(**args),
    "plan_tool_calls": lambda args: plan_tool_calls(**args),
    "create_report_outline": lambda args: create_report_outline(**args),
    "browser_use": lambda args: browser_use(**args),
    "transcribe_audio": lambda args: transcribe_audio(**args),
}


def invoke_adapter(tool_name: str, args: dict[str, Any]) -> dict[str, Any] | None:
    if is_veil_tool(tool_name):
        return call_veil_tool(tool_name, args)
    if is_siem_tool(tool_name):
        return call_siem_tool(tool_name, args)
    if is_nessus_tool(tool_name):
        return call_nessus_tool(tool_name, args)
    adapter = ADAPTERS.get(tool_name)
    if adapter is None:
        return None
    return adapter(args)
