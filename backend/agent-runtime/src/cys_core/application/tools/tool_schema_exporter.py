from __future__ import annotations

from typing import Any

from cys_core.application.datasources.schema_exporter import export_for_family
from cys_core.application.datasources.schema_fetch import fetch_tool_input_schema
from cys_core.domain.datasources.schema_models import ModelFamily


class ToolSchemaExporter:
    """Export LangChain/Pydantic tool schemas for OpenAI/BFCL consumers."""

    def export(self, schema: dict[str, Any], *, family: ModelFamily | str = ModelFamily.OPENAI) -> dict[str, Any]:
        return export_for_family(schema, family)

    def export_tool(
        self,
        tool_name: str,
        tool_registry: Any,
        *,
        family: ModelFamily | str = ModelFamily.OPENAI,
    ) -> dict[str, Any] | None:
        fetched = fetch_tool_input_schema(tool_name, tool_registry, family=family)
        if fetched is None:
            return None
        return fetched.json_schema
