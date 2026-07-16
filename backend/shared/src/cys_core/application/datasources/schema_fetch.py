from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cys_core.application.datasources.schema_exporter import export_for_family
from cys_core.application.datasources.tool_bindings import get_tool_datasource_binding
from cys_core.domain.datasources.schema_models import ModelFamily

GATEWAY_ADAPTER_SCHEMAS: dict[str, dict[str, Any]] = {
    "query_siem_readonly": {
        "type": "object",
        "title": "query_siem_readonly",
        "properties": {
            "query": {"type": "string"},
            "time_range": {"type": "string"},
            "limit": {"type": "integer"},
        },
        "required": ["query"],
    },
    "rag_query": {
        "type": "object",
        "title": "rag_query",
        "properties": {
            "query": {"type": "string"},
            "persona": {"type": "string"},
            "tenant": {"type": "string"},
            "roles": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["query"],
    },
}


@dataclass(frozen=True)
class ToolInputSchema:
    tool_name: str
    json_schema: dict[str, Any]
    pydantic_model: type[Any] | None = None


def fetch_tool_input_schema(
    tool_name: str,
    tool_registry: Any,
    *,
    family: ModelFamily | str = ModelFamily.GENERIC,
) -> ToolInputSchema | None:
    raw: dict[str, Any] | None = None
    model_cls: type[Any] | None = None
    if tool_name in GATEWAY_ADAPTER_SCHEMAS:
        raw = GATEWAY_ADAPTER_SCHEMAS[tool_name]
    else:
        try:
            tool = tool_registry.get(tool_name)
        except Exception:
            return None
        model_cls = getattr(tool, "args_schema", None)
        if model_cls is not None and hasattr(model_cls, "model_json_schema"):
            raw = model_cls.model_json_schema()
    if raw is None:
        binding = get_tool_datasource_binding(tool_name)
        if binding is None:
            return None
        raw = {
            "type": "object",
            "title": tool_name,
            "properties": {},
            "required": [],
        }
    return ToolInputSchema(
        tool_name=tool_name,
        json_schema=export_for_family(raw, family),
        pydantic_model=model_cls,
    )
