from __future__ import annotations

from typing import Any, Callable

from cys_core.infrastructure.tools.adapters.nessus_mcp import call_nessus_tool, is_nessus_tool
from cys_core.infrastructure.tools.adapters.rag import rag_query_tool
from cys_core.infrastructure.tools.adapters.siem import query_siem_readonly_search
from cys_core.infrastructure.tools.adapters.siem_mcp import call_siem_tool, is_siem_tool
from cys_core.infrastructure.tools.adapters.veil_mcp import call_veil_tool, is_veil_tool

AdapterFn = Callable[[dict[str, Any]], dict[str, Any]]

ADAPTERS: dict[str, AdapterFn] = {
    "query_siem_readonly": lambda args: query_siem_readonly_search(**args),
    "rag_query": lambda args: rag_query_tool(**args),
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
