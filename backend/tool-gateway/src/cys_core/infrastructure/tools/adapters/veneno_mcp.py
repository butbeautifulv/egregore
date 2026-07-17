from __future__ import annotations

from typing import Any

from cys_core.integrations.veneno_mcp_client import VENENO_MCP_TOOL_NAMES, call_veneno_mcp_tool


def is_veneno_tool(tool_name: str) -> bool:
    return tool_name in VENENO_MCP_TOOL_NAMES


def call_veneno_tool(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Gateway adapter entrypoint for Veneno execution MCP tools (HITL-gated)."""
    return call_veneno_mcp_tool(tool_name, args)
