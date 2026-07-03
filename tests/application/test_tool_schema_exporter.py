from __future__ import annotations

from pydantic import BaseModel, Field

from cys_core.application.tools.schema_exporter import ToolSchemaExporter


class _Args(BaseModel):
    q: str = Field(description="query")


class _FakeTool:
    name = "fake"
    description = "fake tool"
    args_schema = _Args


def test_schema_exporter_uses_args_schema() -> None:
    exporter = ToolSchemaExporter()
    schema = exporter.export_json_schema(_FakeTool())  # type: ignore[arg-type]
    assert schema["name"] == "fake"
    assert schema["parameters"]["properties"]["q"]["type"] == "string"

