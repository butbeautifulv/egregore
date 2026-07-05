from __future__ import annotations

from cys_core.domain.tools.models import ToolDefinitionView, ToolStatus

DISCOVERY_TOOL_NAMES: frozenset[str] = frozenset({"search_personas", "search_skills", "search_tools"})

DISCOVERY_TOOL_DEFINITIONS: list[ToolDefinitionView] = [
    ToolDefinitionView(name="search_personas", module="discovery", status=ToolStatus.REAL, description="Search persona catalog"),
    ToolDefinitionView(name="search_skills", module="discovery", status=ToolStatus.REAL, description="Search skill catalog"),
    ToolDefinitionView(name="search_tools", module="discovery", status=ToolStatus.REAL, description="Search tool catalog"),
]
