from __future__ import annotations

from typing import Any, Callable

from interfaces.gateways.tool.adapters.rag import rag_query_tool
from interfaces.gateways.tool.adapters.siem import query_siem_readonly_search
from interfaces.gateways.tool.adapters.veil_mcp import call_veil_tool, is_veil_tool

AdapterFn = Callable[[dict[str, Any]], dict[str, Any]]

ADAPTERS: dict[str, AdapterFn] = {
    "query_siem_readonly": lambda args: query_siem_readonly_search(**args),
    "rag_query": lambda args: rag_query_tool(**args),
}


def invoke_adapter(tool_name: str, args: dict[str, Any]) -> dict[str, Any] | None:
    if is_veil_tool(tool_name):
        return call_veil_tool(tool_name, args)
    adapter = ADAPTERS.get(tool_name)
    if adapter is None:
        return None
    return adapter(args)
