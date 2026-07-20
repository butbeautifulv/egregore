from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cys_core.application.use_cases.invoke_tool import InvokeTool
from cys_core.domain.tools.exceptions import HitlRequired, SandboxTokenInvalid, ScopeViolation, ToolChainDepthExceeded
from cys_core.domain.tools.models import ToolInvokeCommand
from cys_core.security.rate_limit import RateLimitExceeded


def _command(**overrides) -> ToolInvokeCommand:
    base = {
        "tool_name": "read_repo_metadata",
        "args": {"repo_path": "/tmp"},
        "persona": "soc",
        "sandbox_id": "sb-1",
    }
    base.update(overrides)
    return ToolInvokeCommand(**base)


async def _adapter_returning(value):
    """invoke_adapter is async (real MCP adapters await network I/O) — tests
    stand in with a coroutine function returning a fixed value."""
    return value


async def _adapter_echoing_name(name, _args):
    return {"adapter": name}


@pytest.mark.unit
async def test_invoke_tool_rejects_tool_with_no_adapter():
    """No fallback to tool_registry.get(...).invoke(...) — a tool with no gateway
    adapter (agent-runtime-internal, e.g. reasoning/orchestration primitives) is
    rejected with a clear error instead of silently executing via the registry.
    See docs/MSP_BACKLOG.md §21.5."""
    registry = MagicMock()
    # .get() raising simulates "no schema hint available" — fetch_tool_input_schema
    # catches this and skips pre-invoke schema validation; the point of this test is
    # that execution itself never reaches .invoke() on whatever .get() would return.
    registry.get.side_effect = KeyError("no schema for this tool")
    recorded: list[tuple[ToolInvokeCommand, object]] = []

    invoke = InvokeTool(
        require_sandbox=lambda _sid: None,
        check_tool_chain=lambda _cmd: None,
        invoke_adapter=lambda _name, _args: _adapter_returning(None),
        tool_registry=registry,
        sanitize_tool_output_or_raise=lambda raw: str(raw),
        record_tool_invocation=lambda cmd, res: recorded.append((cmd, res)),
    )
    result = await invoke.execute(_command(tool_name="reasoning_step"))
    assert result.success is False
    assert "no Tool Gateway adapter" in result.error
    assert len(recorded) == 1


@pytest.mark.unit
async def test_invoke_tool_chain_depth_error():
    invoke = InvokeTool(
        require_sandbox=lambda _sid: None,
        check_tool_chain=lambda _cmd: (_ for _ in ()).throw(ToolChainDepthExceeded("too deep")),
        invoke_adapter=lambda _name, _args: _adapter_returning(None),
        tool_registry=MagicMock(),
        sanitize_tool_output_or_raise=lambda raw: str(raw),
        record_tool_invocation=lambda *_a: None,
    )
    result = await invoke.execute(_command(tool_name="run_active_scan"))
    assert result.success is False
    assert "too deep" in result.error


@pytest.mark.unit
async def test_invoke_tool_rejects_out_of_scope_tool():
    """Scope enforcement happens at the gateway itself, independent of whatever
    checked (or didn't check) scope before the call reached here — the whole
    point of moving this here. See docs/MSP_BACKLOG.md §22-23."""
    invoke = InvokeTool(
        require_sandbox=lambda _sid: None,
        check_tool_chain=lambda _cmd: None,
        invoke_adapter=lambda _name, _args: _adapter_returning({"ok": True}),
        tool_registry=MagicMock(),
        sanitize_tool_output_or_raise=lambda raw: str(raw),
        record_tool_invocation=lambda *_a: None,
        check_scope=lambda _cmd: (_ for _ in ()).throw(ScopeViolation("tool not allowed")),
    )
    result = await invoke.execute(_command(tool_name="run_active_scan"))
    assert result.success is False
    assert "tool not allowed" in result.error


@pytest.mark.unit
async def test_invoke_tool_rejects_over_rate_limit():
    invoke = InvokeTool(
        require_sandbox=lambda _sid: None,
        check_tool_chain=lambda _cmd: None,
        invoke_adapter=lambda _name, _args: _adapter_returning({"ok": True}),
        tool_registry=MagicMock(),
        sanitize_tool_output_or_raise=lambda raw: str(raw),
        record_tool_invocation=lambda *_a: None,
        check_rate_limit=lambda _cmd: (_ for _ in ()).throw(RateLimitExceeded("too many calls")),
    )
    result = await invoke.execute(_command(tool_name="run_active_scan"))
    assert result.success is False
    assert "too many calls" in result.error


@pytest.mark.unit
async def test_invoke_tool_rejects_invalid_sandbox_token():
    """docs/MSP_BACKLOG.md §11.5/§37: mint_sandbox_token() minted a token
    nothing verified for a long time — this proves the gateway rejects on its own
    check_sandbox_token result, independent of whatever the caller did or didn't verify."""
    invoke = InvokeTool(
        require_sandbox=lambda _sid: None,
        check_tool_chain=lambda _cmd: None,
        invoke_adapter=lambda _name, _args: _adapter_returning({"ok": True}),
        tool_registry=MagicMock(),
        sanitize_tool_output_or_raise=lambda raw: str(raw),
        record_tool_invocation=lambda *_a: None,
        check_sandbox_token=lambda _cmd: (_ for _ in ()).throw(SandboxTokenInvalid("missing_sandbox_token")),
    )
    result = await invoke.execute(_command(tool_name="run_active_scan"))
    assert result.success is False
    assert "missing_sandbox_token" in result.error


@pytest.mark.unit
async def test_invoke_tool_refuses_pending_hitl_approval_instead_of_executing():
    """docs/MSP_BACKLOG.md §35/§58: the tool adapter must never run when check_hitl
    says the call needs a human — this is the refuse-then-retry design's core guarantee."""
    executed = False

    async def _adapter(_name, _args):
        nonlocal executed
        executed = True
        return {"ok": True}

    invoke = InvokeTool(
        require_sandbox=lambda _sid: None,
        check_tool_chain=lambda _cmd: None,
        invoke_adapter=_adapter,
        tool_registry=MagicMock(),
        sanitize_tool_output_or_raise=lambda raw: str(raw),
        record_tool_invocation=lambda *_a: None,
        check_hitl=lambda _cmd: (_ for _ in ()).throw(
            HitlRequired(risk_level="high", approval_token="tok-1")
        ),
    )
    result = await invoke.execute(_command(tool_name="run_playbook"))
    assert result.success is False
    assert result.error == "hitl_required"
    assert result.hitl_required is True
    assert result.risk_level == "high"
    assert result.approval_token == "tok-1"
    assert executed is False


@pytest.mark.unit
async def test_invoke_tool_defaults_check_scope_and_rate_limit_to_noop():
    """Callers that predate check_scope/check_rate_limit/check_sandbox_token (existing
    production wiring elsewhere, other tests) must keep working unchanged."""
    invoke = InvokeTool(
        require_sandbox=lambda _sid: None,
        check_tool_chain=lambda _cmd: None,
        invoke_adapter=_adapter_echoing_name,
        tool_registry=MagicMock(),
        sanitize_tool_output_or_raise=lambda raw: str(raw),
        record_tool_invocation=lambda *_a: None,
    )
    result = await invoke.execute(_command(tool_name="run_active_scan"))
    assert result.success is True


@pytest.mark.unit
async def test_invoke_tool_uses_adapter_when_present():
    invoke = InvokeTool(
        require_sandbox=lambda _sid: None,
        check_tool_chain=lambda _cmd: None,
        invoke_adapter=_adapter_echoing_name,
        tool_registry=MagicMock(),
        sanitize_tool_output_or_raise=lambda raw: str(raw),
        record_tool_invocation=lambda *_a: None,
    )
    result = await invoke.execute(_command(tool_name="custom_adapter_tool"))
    assert result.success is True
    assert result.data == {"adapter": "custom_adapter_tool"}
