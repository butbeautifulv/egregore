from __future__ import annotations

from cys_core.application.tools.providers.discovery import DISCOVERY_TOOL_DEFINITIONS
from cys_core.application.tools.providers.orchestration import ORCHESTRATION_TOOL_DEFINITIONS
from cys_core.application.tools.providers.rag import RAG_TOOL_DEFINITIONS
from cys_core.application.tools.providers.sandbox import SANDBOX_TOOL_DEFINITIONS, sandbox_tool_status
from cys_core.application.tools.providers.siem import SIEM_TOOL_DEFINITIONS
from cys_core.application.tools.providers.web import WEB_TOOL_DEFINITIONS
from cys_core.domain.tools.models import ToolDefinitionView, ToolStatus

ALL_PROVIDER_DEFINITIONS: list[ToolDefinitionView] = [
    *DISCOVERY_TOOL_DEFINITIONS,
    *RAG_TOOL_DEFINITIONS,
    *SIEM_TOOL_DEFINITIONS,
    *SANDBOX_TOOL_DEFINITIONS,
    *WEB_TOOL_DEFINITIONS,
    *ORCHESTRATION_TOOL_DEFINITIONS,
]

MODULE_BY_TOOL_NAME: dict[str, ToolDefinitionView] = {item.name: item for item in ALL_PROVIDER_DEFINITIONS}


def status_for_tool(tool_name: str) -> ToolStatus:
    if tool_name in {"run_active_scan", "python_sandbox", "browser_use"}:
        return sandbox_tool_status(tool_name)
    module_def = MODULE_BY_TOOL_NAME.get(tool_name)
    return module_def.status if module_def else ToolStatus.REAL
