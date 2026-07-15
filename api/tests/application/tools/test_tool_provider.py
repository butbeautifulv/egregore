from __future__ import annotations

import pytest

from cys_core.application.tools.registry_provider import RegistryToolProvider, get_default_tool_provider
from cys_core.application.tools.tool_schema_exporter import ToolSchemaExporter
from cys_core.domain.datasources.schema_models import ModelFamily
from cys_core.domain.tools.models import ToolInvokeCommand, ToolStatus
from cys_core.registry.tools import tool_registry


@pytest.mark.unit
def test_tool_definition_view_includes_module_metadata() -> None:
    provider = RegistryToolProvider(tool_registry=tool_registry)
    names = {item.name: item for item in provider.definitions(profile_id="cybersec-soc")}
    assert names["query_siem_readonly"].module == "siem"
    assert names["rag_query"].module == "rag"
    assert names["search_tools"].module == "discovery"
    assert names["query_siem_readonly"].datasource_id == "siem-readonly"


@pytest.mark.unit
def test_tool_status_stub_for_disabled_veneno_scan() -> None:
    provider = RegistryToolProvider(tool_registry=tool_registry)
    names = {item.name: item for item in provider.definitions(profile_id="cybersec-soc")}
    assert names["run_active_scan"].status == ToolStatus.STUB


@pytest.mark.unit
def test_tool_schema_exporter_openai_shape() -> None:
    exporter = ToolSchemaExporter()
    schema = exporter.export_tool("read_repo_metadata", tool_registry, family=ModelFamily.OPENAI)
    assert schema is not None
    assert schema["additionalProperties"] is False
    assert "repo_path" in schema["properties"]


@pytest.mark.unit
def test_registry_provider_resolve_returns_langchain_tools() -> None:
    from bootstrap.container import get_container

    provider = get_container().get_tool_registry_port()
    registry_provider = RegistryToolProvider(tool_registry=provider)
    tools = registry_provider.resolve(["web_search"], profile_id="general-assistant")
    assert len(tools) == 1
    assert tools[0].name == "web_search"


@pytest.mark.unit
def test_local_gateway_invokes_siem_tool() -> None:
    from bootstrap.container import get_container

    gateway = get_container().get_tool_execution_gateway()
    result = gateway.invoke(
        ToolInvokeCommand(
            tool_name="query_siem_readonly",
            args={"query": "powershell"},
            persona="soc",
            sandbox_id="sandbox-1",
            profile_id="cybersec-soc",
        )
    )
    assert result.success is True


@pytest.mark.unit
def test_sandbox_and_web_module_metadata() -> None:
    provider = RegistryToolProvider(tool_registry=tool_registry)
    names = {item.name: item for item in provider.definitions(profile_id="cybersec-soc")}
    assert names["python_sandbox"].module == "sandbox"
    assert names["web_search"].module == "web"
    assert names["ask_user"].module == "orchestration"
    assert names["spawn_worker"].module == "orchestration"


@pytest.mark.unit
def test_tool_matrix_markdown_contains_modules() -> None:
    from cys_core.application.tools.tool_matrix import render_tool_matrix_markdown

    md = render_tool_matrix_markdown(profile_ids=["cybersec-soc"])
    assert "## Profile: `cybersec-soc`" in md
    assert "| `query_siem_readonly` | siem |" in md
    assert "| `python_sandbox` | sandbox |" in md
    assert "| `web_search` | web |" in md
    assert "| `ask_user` | orchestration |" in md


@pytest.mark.unit
def test_bfcl_sample_categories_export_schemas() -> None:
    """Smoke: representative tools export strict object schemas."""
    exporter = ToolSchemaExporter()
    samples = ["read_repo_metadata", "query_siem_readonly", "rag_query", "search_tools"]
    for name in samples:
        schema = exporter.export_tool(name, tool_registry, family=ModelFamily.OPENAI)
        assert schema is not None
        assert schema.get("type") == "object"
        assert schema.get("additionalProperties") is False
