from __future__ import annotations

from cys_core.domain.tools.models import ToolDefinitionView, ToolStatus

SANDBOX_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "python_sandbox",
        "browser_use",
        "execute_command",
        "run_active_scan",
    }
)


def sandbox_tool_status(tool_name: str) -> ToolStatus:
    if tool_name == "run_active_scan":
        try:
            from cys_core.integrations.veneno_mcp_client import veneno_mcp_enabled

            return ToolStatus.REAL if veneno_mcp_enabled() else ToolStatus.STUB
        except Exception:
            return ToolStatus.STUB
    if tool_name == "python_sandbox":
        try:
            from cys_core.application.runtime_config import get_e2b_api_key

            return ToolStatus.REAL if get_e2b_api_key().strip() else ToolStatus.STUB
        except Exception:
            return ToolStatus.STUB
    if tool_name == "browser_use":
        try:
            from cys_core.application.runtime_config import get_browser_enabled

            return ToolStatus.REAL if get_browser_enabled() else ToolStatus.STUB
        except Exception:
            return ToolStatus.STUB
    return ToolStatus.REAL


SANDBOX_TOOL_DEFINITIONS: list[ToolDefinitionView] = [
    ToolDefinitionView(
        name="python_sandbox",
        module="sandbox",
        status=sandbox_tool_status("python_sandbox"),
        description="Execute Python in isolated sandbox",
    ),
    ToolDefinitionView(
        name="browser_use",
        module="sandbox",
        status=sandbox_tool_status("browser_use"),
        description="Browser automation for authorized URLs",
    ),
    ToolDefinitionView(
        name="execute_command",
        module="sandbox",
        status=ToolStatus.REAL,
        description="Execute shell command (HITL)",
    ),
    ToolDefinitionView(
        name="run_active_scan",
        module="sandbox",
        status=sandbox_tool_status("run_active_scan"),
        description="Active security scan via Veneno MCP",
    ),
]
