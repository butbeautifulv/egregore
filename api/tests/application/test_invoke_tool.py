from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cys_core.application.use_cases.invoke_tool import InvokeTool
from cys_core.domain.tools.exceptions import ToolChainDepthExceeded
from cys_core.domain.tools.models import ToolInvokeCommand


def _command(**overrides) -> ToolInvokeCommand:
    base = {
        "tool_name": "read_repo_metadata",
        "args": {"repo_path": "/tmp"},
        "persona": "soc",
        "sandbox_id": "sb-1",
    }
    base.update(overrides)
    return ToolInvokeCommand(**base)


@pytest.mark.unit
def test_invoke_tool_executes_registry_tool():
    registry = MagicMock()
    registry.get.return_value = MagicMock(invoke=MagicMock(return_value={"ok": True}))
    recorded: list[tuple[ToolInvokeCommand, object]] = []

    invoke = InvokeTool(
        require_sandbox=lambda _sid: None,
        check_tool_chain=lambda _cmd: None,
        invoke_adapter=lambda _name, _args: None,
        tool_registry=registry,
        sanitize_tool_output_or_raise=lambda raw: str(raw),
        record_tool_invocation=lambda cmd, res: recorded.append((cmd, res)),
    )
    result = invoke.execute(_command())
    assert result.success is True
    assert result.data == {"ok": True}
    assert len(recorded) == 1


@pytest.mark.unit
def test_invoke_tool_chain_depth_error():
    invoke = InvokeTool(
        require_sandbox=lambda _sid: None,
        check_tool_chain=lambda _cmd: (_ for _ in ()).throw(ToolChainDepthExceeded("too deep")),
        invoke_adapter=lambda _name, _args: None,
        tool_registry=MagicMock(),
        sanitize_tool_output_or_raise=lambda raw: str(raw),
        record_tool_invocation=lambda *_a: None,
    )
    result = invoke.execute(_command(tool_name="run_active_scan"))
    assert result.success is False
    assert "too deep" in result.error


@pytest.mark.unit
def test_invoke_tool_uses_adapter_when_present():
    invoke = InvokeTool(
        require_sandbox=lambda _sid: None,
        check_tool_chain=lambda _cmd: None,
        invoke_adapter=lambda name, _args: {"adapter": name},
        tool_registry=MagicMock(),
        sanitize_tool_output_or_raise=lambda raw: str(raw),
        record_tool_invocation=lambda *_a: None,
    )
    result = invoke.execute(_command(tool_name="custom_adapter_tool"))
    assert result.success is True
    assert result.data == {"adapter": "custom_adapter_tool"}
