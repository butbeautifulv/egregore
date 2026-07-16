from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cys_core.application.authz.service import AuthzService
from cys_core.application.use_cases.invoke_tool import InvokeTool
from cys_core.domain.tools.models import ToolInvokeCommand


class _DenyAuthzPort:
    def check(self, _req):
        return False

    def list_objects(self, **kwargs):
        return []

    def write_tuples(self, tuples):
        return None

    def delete_tuples(self, tuples):
        return None

    def ping(self):
        return True


class _FakeDatasourceCatalog:
    def get(self, datasource_id: str):
        from cys_core.domain.datasources.models import DataSource, DataSourceCapability

        return DataSource(
            id=datasource_id,
            type=datasource_id,
            capabilities=[
                DataSourceCapability.GET,
                DataSourceCapability.LIST,
                DataSourceCapability.QUERY,
            ],
        )


@pytest.mark.unit
def test_invoke_tool_denies_siem_without_workspace_grant(monkeypatch: pytest.MonkeyPatch) -> None:
    from cys_core.application.datasources import providers

    monkeypatch.setattr(providers, "_catalog", _FakeDatasourceCatalog())
    authz = AuthzService(_DenyAuthzPort(), mode="enforce")
    invoke = InvokeTool(
        require_sandbox=lambda _sid: None,
        check_tool_chain=lambda _cmd: None,
        invoke_adapter=lambda _name, _args: None,
        tool_registry=MagicMock(),
        sanitize_tool_output_or_raise=lambda raw: str(raw),
        record_tool_invocation=lambda *_a: None,
        authz_service=authz,
    )
    command = ToolInvokeCommand(
        tool_name="query_siem_readonly",
        args={"query": "test"},
        persona="soc",
        sandbox_id="sb-1",
        workspace_id="ws-no-siem",
    )
    result = invoke.execute(command)
    assert result.success is False
    assert result.error == "AUTHZ_DENIED"
