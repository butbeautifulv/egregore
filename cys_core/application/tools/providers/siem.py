from __future__ import annotations

from cys_core.domain.tools.models import ToolDefinitionView, ToolStatus

SIEM_TOOL_NAMES: frozenset[str] = frozenset({"query_siem_readonly"})

SIEM_TOOL_DEFINITIONS: list[ToolDefinitionView] = [
    ToolDefinitionView(
        name="query_siem_readonly",
        module="siem",
        status=ToolStatus.REAL,
        datasource_id="siem-readonly",
        description="Read-only SIEM search",
    ),
]
