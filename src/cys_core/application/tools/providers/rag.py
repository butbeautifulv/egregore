from __future__ import annotations

from cys_core.domain.tools.models import ToolDefinitionView, ToolStatus

RAG_TOOL_NAMES: frozenset[str] = frozenset({"rag_query"})

RAG_TOOL_DEFINITIONS: list[ToolDefinitionView] = [
    ToolDefinitionView(
        name="rag_query",
        module="rag",
        status=ToolStatus.REAL,
        datasource_id="rag-index",
        description="Read-only RAG retrieval",
    ),
]
