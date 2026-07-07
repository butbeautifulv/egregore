from __future__ import annotations

from typing import Any

from cys_core.integrations.siem_mcp_client import SIEM_MCP_TOOL_NAMES, call_siem_mcp_tool


def is_siem_tool(tool_name: str) -> bool:
    return tool_name in SIEM_MCP_TOOL_NAMES


def call_siem_tool(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Gateway adapter entrypoint for MaxPatrol SIEM MCP tools."""
    return call_siem_mcp_tool(tool_name, args)
