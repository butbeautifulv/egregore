from __future__ import annotations

import pytest

from cys_core.application.datasources.args_validation import validate_tool_args
from cys_core.application.datasources.model_family import export_options_for_family, knobs_for_model_family
from cys_core.application.datasources.schema_exporter import export_for_family, export_json_schema
from cys_core.application.datasources.schema_fetch import fetch_tool_input_schema
from cys_core.domain.datasources.schema_models import ModelFamily
from cys_core.infrastructure.datasources.audit_sink import clear_datasource_audit_events, get_datasource_audit_events
from cys_core.registry.tools import tool_registry
from interfaces.gateways.tool.handler import invoke_tool
from interfaces.gateways.tool.models import ToolInvokeRequest


@pytest.fixture(autouse=True)
def _clear_audit() -> None:
    clear_datasource_audit_events()
    yield
    clear_datasource_audit_events()


@pytest.mark.unit
def test_openai_knobs_enable_strict_additional_properties() -> None:
    knobs = knobs_for_model_family(ModelFamily.OPENAI)
    assert knobs.strict_additional_properties is True
    assert knobs.reject_unknown_args is True


@pytest.mark.unit
def test_schema_exporter_sets_additional_properties_false() -> None:
    raw = {
        "type": "object",
        "properties": {"query": {"type": "string"}},
    }
    exported = export_json_schema(raw, options=export_options_for_family(ModelFamily.OPENAI))
    assert exported["additionalProperties"] is False
    assert exported["required"] == ["query"]


@pytest.mark.unit
def test_schema_exporter_normalizes_required_fields() -> None:
    raw = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "limit": {"type": "integer"},
        },
    }
    exported = export_for_family(raw, ModelFamily.OPENAI)
    assert sorted(exported["required"]) == ["limit", "query"]


@pytest.mark.unit
def test_fetch_gateway_adapter_schema() -> None:
    schema = fetch_tool_input_schema("query_siem_readonly", tool_registry, family=ModelFamily.OPENAI)
    assert schema is not None
    assert schema.json_schema["required"] == ["query"]
    assert schema.json_schema["additionalProperties"] is False


@pytest.mark.unit
def test_fetch_registry_tool_schema() -> None:
    schema = fetch_tool_input_schema("read_repo_metadata", tool_registry, family=ModelFamily.OPENAI)
    assert schema is not None
    assert "repo_path" in schema.json_schema["properties"]


@pytest.mark.unit
def test_validate_tool_args_rejects_missing_required() -> None:
    schema = fetch_tool_input_schema("query_siem_readonly", tool_registry, family=ModelFamily.OPENAI)
    assert schema is not None
    errors = validate_tool_args({}, schema, family=ModelFamily.OPENAI)
    assert any("query" in err for err in errors)


@pytest.mark.unit
def test_validate_tool_args_accepts_valid_payload() -> None:
    schema = fetch_tool_input_schema("query_siem_readonly", tool_registry, family=ModelFamily.OPENAI)
    assert schema is not None
    errors = validate_tool_args({"query": "alert"}, schema, family=ModelFamily.OPENAI)
    assert errors == []


@pytest.mark.unit
def test_invoke_tool_rejects_schema_mismatch() -> None:
    response = invoke_tool(
        ToolInvokeRequest(
            tool_name="query_siem_readonly",
            args={},
            persona="soc",
            sandbox_id="sandbox-1",
            profile_id="cybersec-soc",
        )
    )
    assert response.success is False
    assert response.error == "schema_mismatch"
    assert response.data["schema_mismatch"]["code"] == "schema_mismatch"
    events = get_datasource_audit_events()
    assert any(event.get("kind") == "schema_mismatch" for event in events)


@pytest.mark.unit
def test_invoke_tool_allows_valid_siem_args() -> None:
    response = invoke_tool(
        ToolInvokeRequest(
            tool_name="query_siem_readonly",
            args={"query": "powershell"},
            persona="soc",
            sandbox_id="sandbox-1",
            profile_id="cybersec-soc",
        )
    )
    assert response.success is True
