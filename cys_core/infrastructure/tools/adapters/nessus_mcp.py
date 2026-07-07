from __future__ import annotations

from typing import Any

from cys_core.integrations.nessus_mcp_client import NESSUS_MCP_TOOL_NAMES, call_nessus_mcp_tool


def is_nessus_tool(tool_name: str) -> bool:
    return tool_name in NESSUS_MCP_TOOL_NAMES


def call_nessus_tool(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    return call_nessus_mcp_tool(tool_name, args)
