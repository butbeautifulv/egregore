from __future__ import annotations

import pytest

from cys_core.application.datasources.attach_filter import filter_attachable_tools
from cys_core.application.use_cases.invoke_tool import InvokeTool
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID
from cys_core.domain.datasources.authz import AuthorizationDecision
from cys_core.infrastructure.datasources.audit_sink import clear_datasource_audit_events, get_datasource_audit_events
from interfaces.gateways.tool.handler import invoke_tool
from interfaces.gateways.tool.models import ToolInvokeRequest


@pytest.fixture(autouse=True)
def _clear_audit() -> None:
    # get_container() wires configure_datasource_catalog/configure_datasource_audit
    # (module-level globals, not reset by resetting the container reference
    # itself) — filter_attachable_tools()/authorize_tool_datasource() fail
    # closed without it. The tests below that call invoke_tool() (which calls
    # get_container() internally) happen to wire this as a side effect, but
    # the two that only call filter_attachable_tools() directly do not — so
    # this must not depend on test run order/which test happens to run first.
    from bootstrap.container import get_container

    get_container()
    clear_datasource_audit_events()
    yield
    clear_datasource_audit_events()


@pytest.mark.unit
def test_attach_filter_drops_non_get_tools_for_general_assistant() -> None:
    tools = ["query_siem_readonly", "rag_query", "read_repo_metadata"]
    filtered = filter_attachable_tools(tools, profile_id="general-assistant", persona="consultant")
    assert "read_repo_metadata" in filtered
    assert "query_siem_readonly" not in filtered
    assert "rag_query" not in filtered


@pytest.mark.unit
def test_attach_filter_keeps_siem_for_cybersec_soc() -> None:
    tools = ["query_siem_readonly", "rag_query", "read_repo_metadata"]
    filtered = filter_attachable_tools(tools, profile_id=DEFAULT_PROFILE_ID, persona="soc")
    assert "query_siem_readonly" in filtered
    assert "rag_query" in filtered
    assert "read_repo_metadata" in filtered


@pytest.mark.unit
async def test_invoke_tool_denies_mutate_capability_without_grant(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "cys_core.application.use_cases.invoke_tool.authorize_tool_datasource",
        lambda **kwargs: AuthorizationDecision(
            allowed=False,
            reason="capability_not_granted",
            matched_rule="get_only_default",
            tags=["deny", "capability"],
        ),
    )

    async def _adapter(_name, _args):
        return {"ok": True}

    use_case = InvokeTool(
        require_sandbox=lambda _sid: None,
        check_tool_chain=lambda _req: None,
        invoke_adapter=_adapter,
        tool_registry=__import__("unittest.mock", fromlist=["MagicMock"]).MagicMock(),
        sanitize_tool_output_or_raise=lambda data: str(data),
        record_tool_invocation=lambda *_a: None,
    )
    response = await use_case.execute(
        ToolInvokeRequest(
            tool_name="query_siem_readonly",
            args={"query": "x"},
            persona="consultant",
            sandbox_id="sandbox-1",
            profile_id="general-assistant",
        )
    )
    assert response.success is False
    assert response.error == "capability_not_granted"
    assert response.data["deny"]["code"] == "datasource_denied"
    assert response.data["deny"]["matched_rule"] == "get_only_default"


@pytest.mark.unit
async def test_invoke_tool_exec_denies_general_assistant_siem() -> None:
    response = await invoke_tool(
        ToolInvokeRequest(
            tool_name="query_siem_readonly",
            args={"query": "test"},
            persona="consultant",
            sandbox_id="sandbox-1",
            profile_id="general-assistant",
        )
    )
    assert response.success is False
    deny = response.data.get("deny", {})
    assert deny.get("code") == "datasource_denied"
    assert deny.get("reason") in {"capability_not_granted", "not_in_profile_allowlist"}


@pytest.mark.unit
async def test_deny_emits_policy_and_tool_audit_events() -> None:
    await invoke_tool(
        ToolInvokeRequest(
            tool_name="rag_query",
            args={"query": "q"},
            persona="consultant",
            sandbox_id="sandbox-1",
            profile_id="general-assistant",
        )
    )
    events = get_datasource_audit_events()
    assert len(events) >= 1
    event = events[-1]
    assert event["kind"] == "policy"
    assert event["allowed"] is False
    assert "policy_event" in event
    assert "tool_event" in event
    assert event["policy_event"]["type"] == "policy"
    assert event["tool_event"]["type"] == "tool"
