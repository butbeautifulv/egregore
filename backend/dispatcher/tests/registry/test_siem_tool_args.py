from __future__ import annotations

import json

import httpx
import pytest

from cys_core.application.reasoning.sgr_tooling import scope_allowed_tools
from cys_core.application.runs.tool_coercion import normalize_siem_tool_args
from cys_core.domain.agents.models import AgentDefinition
from cys_core.integrations.siem_mcp_client import call_siem_mcp_tool
from cys_core.registry.siem_tools import make_siem_tool
from interfaces.gateways.tool.adapters.siem_mcp import call_siem_tool


@pytest.mark.unit
def test_normalize_siem_tool_args_unwraps_kwargs_id_alias() -> None:
    result = normalize_siem_tool_args(
        "investigate_incident",
        {"kwargs": {"id": "024526f2-f434-4d60-a22f-e5ef6efc9212"}},
    )
    assert result == {"incident_id": "024526f2-f434-4d60-a22f-e5ef6efc9212"}


@pytest.mark.unit
def test_normalize_siem_tool_args_maps_top_level_id() -> None:
    result = normalize_siem_tool_args("investigate_incident", {"id": "inc-1"})
    assert result == {"incident_id": "inc-1"}


@pytest.mark.unit
def test_normalize_siem_tool_args_preserves_incident_id() -> None:
    result = normalize_siem_tool_args(
        "investigate_incident",
        {"incident_id": "024526f2-f434-4d60-a22f-e5ef6efc9212", "events_limit": "10"},
    )
    assert result["incident_id"] == "024526f2-f434-4d60-a22f-e5ef6efc9212"
    assert result["events_limit"] == 10


def _patch_invoke_mcp_sync(monkeypatch: pytest.MonkeyPatch, mock_client: httpx.Client) -> None:
    def _fake_invoke_mcp_sync(**kwargs: object) -> dict:
        response = mock_client.post(kwargs.get("url", ""), json=kwargs.get("payload"))
        return response.json()

    monkeypatch.setattr(
        "cys_core.integrations.siem_mcp_client.invoke_mcp_sync",
        _fake_invoke_mcp_sync,
    )


@pytest.mark.unit
def test_call_siem_tool_normalizes_kwargs_before_mcp(monkeypatch: pytest.MonkeyPatch) -> None:
    import cys_core.application.runtime_config as rc

    monkeypatch.setattr(rc, "_siem_mcp_enabled", True)
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        captured["arguments"] = body["params"]["arguments"]
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {"content": [{"type": "text", "text": json.dumps({"ok": True})}]},
            },
        )

    _patch_invoke_mcp_sync(monkeypatch, httpx.Client(transport=httpx.MockTransport(handler)))

    result = call_siem_tool(
        "investigate_incident",
        {"kwargs": {"id": "024526f2-f434-4d60-a22f-e5ef6efc9212"}},
    )
    assert result["success"] is True
    assert captured["arguments"] == {"incident_id": "024526f2-f434-4d60-a22f-e5ef6efc9212"}


@pytest.mark.unit
def test_call_siem_mcp_tool_marks_validation_error_as_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    import cys_core.application.runtime_config as rc

    monkeypatch.setattr(rc, "_siem_mcp_enabled", True)

    validation_text = (
        "1 validation error for call[investigate_incident]\nincident_id\n"
        "  Missing required argument [type=missing_argument, input_value={}, input_type=dict]"
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {"content": [{"type": "text", "text": validation_text}]},
            },
        )

    _patch_invoke_mcp_sync(monkeypatch, httpx.Client(transport=httpx.MockTransport(handler)))
    result = call_siem_mcp_tool("investigate_incident", {"incident_id": "INC-42"})
    assert result["success"] is False
    assert "validation error for call[" in result["error"]


@pytest.mark.unit
def test_call_siem_mcp_tool_marks_siem_api_error_as_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    import cys_core.application.runtime_config as rc

    monkeypatch.setattr(rc, "_siem_mcp_enabled", True)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": "Error calling tool 'investigate_incident': SIEM API error 400: BadRequest",
                        }
                    ]
                },
            },
        )

    _patch_invoke_mcp_sync(monkeypatch, httpx.Client(transport=httpx.MockTransport(handler)))
    result = call_siem_mcp_tool("investigate_incident", {"incident_id": "INC-42"})
    assert result["success"] is False
    assert "SIEM API error" in result["error"]


@pytest.mark.unit
def test_scope_allowed_tools_includes_load_skill_when_skills_configured() -> None:
    defn = AgentDefinition(
        name="soc",
        description="d",
        role="worker",
        system_prompt="x",
        system_prompt_digest="dig",
        schema_name="SocFinding",
        tools=["investigate_incident"],
        skills=["siem-investigation"],
        hitl_tools={},
        reasoning_mode="sgr_hybrid",
    )
    allowed = scope_allowed_tools(defn, "cybersec-soc")
    assert "load_skill" in allowed
    assert "investigate_incident" in allowed


@pytest.mark.unit
def test_investigate_incident_structured_tool_has_args_schema() -> None:
    tool = make_siem_tool("investigate_incident", "test")
    schema = tool.args_schema.model_json_schema()
    assert "incident_id" in schema.get("properties", {})
