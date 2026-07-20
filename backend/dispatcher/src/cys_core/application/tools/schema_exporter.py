from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool


class ToolSchemaExporter:
    """Export tool schemas for function-calling suites (OpenAI/BFCL-style).

    Today we rely on `args_schema` when available; this keeps us decoupled from
    external benchmark repos while producing stable JSON Schema.
    """

    def export_json_schema(self, tool: BaseTool) -> dict[str, Any]:
        schema: dict[str, Any] = {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": {"type": "object", "properties": {}, "required": []},
        }
        args_schema = getattr(tool, "args_schema", None)
        if args_schema is None:
            return schema
        try:
            json_schema = args_schema.model_json_schema()
        except Exception:
            return schema
        props = json_schema.get("properties", {}) if isinstance(json_schema, dict) else {}
        required = json_schema.get("required", []) if isinstance(json_schema, dict) else []
        schema["parameters"] = {"type": "object", "properties": props, "required": required}
        return schema

