from __future__ import annotations

from typing import Any

from cys_core.integrations.veil_mcp_client import VEIL_MCP_TOOL_NAMES, call_veil_mcp_tool


def is_veil_tool(tool_name: str) -> bool:
    return tool_name in VEIL_MCP_TOOL_NAMES


def call_veil_tool(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Gateway adapter entrypoint for Veil knowledge MCP tools."""
    return call_veil_mcp_tool(tool_name, args)
