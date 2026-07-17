from __future__ import annotations

from cys_core.domain.tools.models import ToolDefinitionView, ToolStatus

WEB_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "web_search",
        "read_document",
        "search_archived_webpage",
        "vision_analyze",
        "transcribe_audio",
    }
)

WEB_TOOL_DEFINITIONS: list[ToolDefinitionView] = [
    ToolDefinitionView(name="web_search", module="web", status=ToolStatus.REAL, description="Web search"),
    ToolDefinitionView(name="read_document", module="web", status=ToolStatus.REAL, description="Read local document"),
    ToolDefinitionView(
        name="search_archived_webpage",
        module="web",
        status=ToolStatus.REAL,
        description="Archived webpage lookup",
    ),
    ToolDefinitionView(
        name="vision_analyze",
        module="web",
        status=ToolStatus.REAL,
        description="Vision / image analysis",
    ),
    ToolDefinitionView(
        name="transcribe_audio",
        module="web",
        status=ToolStatus.REAL,
        description="Audio transcription",
    ),
]
