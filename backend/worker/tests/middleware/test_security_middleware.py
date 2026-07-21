from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import ToolMessage


def request(name: str, *, args: dict | None = None, call_id: str = "call-1"):
    return SimpleNamespace(tool_call={"name": name, "args": args or {}, "id": call_id})


def fake_policy_port():
    from cys_core.domain.catalog.models import ProfilePolicyPayload

    payload = ProfilePolicyPayload()
    return SimpleNamespace(
        get_policy=lambda _profile_id: payload,
        get_hitl_threshold=lambda _profile_id: payload.hitl_auto_approve_threshold,
    )


@pytest.mark.unit
def test_security_middleware_paths_and_hitl_builder(monkeypatch):
    import cys_core.middleware.security_middleware as security_middleware

    middleware = security_middleware.SecurityMiddleware("agent-a", "session-a", policy_port=fake_policy_port())
    middleware.rate_limiter = SimpleNamespace(check=MagicMock())
    middleware.monitor = SimpleNamespace(log_security_event=MagicMock(), log_tool_call=MagicMock())
    middleware.stage = "dev"

    class HighRisk:
        value = "high"

        def __gt__(self, _other):
            return True

        def __le__(self, _other):
            return False

    monkeypatch.setattr(security_middleware, "classify_tool_risk_pure", lambda _name, _policy=None: HighRisk())
    gated = middleware.wrap_tool_call(request("danger"), lambda req: ToolMessage(content="ok", tool_call_id="x"))
    assert gated.status == "error"
    assert "requires human approval" in gated.content

    middleware.rate_limiter.check.side_effect = RuntimeError("too many")

    def ok_handler(req):
        return ToolMessage(content="ok", tool_call_id="x")

    limited = middleware.wrap_tool_call(request("parse_netflow"), ok_handler)
    assert limited.status == "error"
    middleware.monitor.log_security_event.assert_called()

    middleware.rate_limiter.check.side_effect = None
    from cys_core.domain.security.risk import RiskLevel

    monkeypatch.setattr(security_middleware, "classify_tool_risk_pure", lambda _name, _policy=None: RiskLevel.LOW)
    handled = middleware.wrap_tool_call(
        request("parse_netflow"),
        lambda req: ToolMessage(content="ok", tool_call_id=req.tool_call["id"]),
    )
    assert handled.content == "ok"
    middleware.monitor.log_tool_call.assert_called()

    with pytest.raises(ValueError, match="handler failed"):
        middleware.wrap_tool_call(
            request("parse_netflow"),
            lambda _req: (_ for _ in ()).throw(ValueError("handler failed")),
        )

    from cys_core.domain.agents.policies import build_interrupt_on

    assert "run_active_scan" in build_interrupt_on({"run_active_scan": True, "read_repo_metadata": False})


@pytest.mark.unit
def test_security_middleware_interrupts_in_prod(monkeypatch):
    import cys_core.middleware.security_middleware as security_middleware

    middleware = security_middleware.SecurityMiddleware(
        "redteam",
        "worker:redteam:job-1",
        policy_port=fake_policy_port(),
    )
    middleware.rate_limiter = SimpleNamespace(check=MagicMock())
    middleware.monitor = SimpleNamespace(log_security_event=MagicMock(), log_tool_call=MagicMock())
    middleware.stage = "prod"
    monkeypatch.setattr(security_middleware, "register_hitl_pause", lambda preview: None)
    monkeypatch.setattr(security_middleware, "interrupt", lambda preview: {"decision": "approve"})

    class HighRisk:
        value = "high"

        def __gt__(self, _other):
            return True

        def __le__(self, _other):
            return False

    monkeypatch.setattr(security_middleware, "classify_tool_risk_pure", lambda _name, _policy=None: HighRisk())
    result = middleware.wrap_tool_call(
        request("run_active_scan", args={"target": "lab"}),
        lambda req: ToolMessage(content="ok", tool_call_id=req.tool_call["id"]),
    )
    assert result.content == "ok"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_security_middleware_async_paths(monkeypatch):
    import cys_core.middleware.security_middleware as security_middleware

    middleware = security_middleware.SecurityMiddleware("agent-a", "session-a", policy_port=fake_policy_port())

    class FakeRateLimiter:
        def __init__(self):
            self.error: Exception | None = None

        async def acheck(self, _key):
            if self.error:
                raise self.error

    rate_limiter = FakeRateLimiter()
    middleware.rate_limiter = rate_limiter
    middleware.monitor = SimpleNamespace(log_security_event=MagicMock(), log_tool_call=MagicMock())
    middleware.stage = "prod"
    monkeypatch.setattr(security_middleware, "register_hitl_pause", lambda preview: None)
    monkeypatch.setattr(security_middleware, "interrupt", lambda preview: {"decision": "reject"})

    class HighRisk:
        value = "high"

        def __gt__(self, _other):
            return True

        def __le__(self, _other):
            return False

    monkeypatch.setattr(security_middleware, "classify_tool_risk_pure", lambda _name, _policy=None: HighRisk())
    gated = await middleware.awrap_tool_call(request("danger"), lambda req: ToolMessage(content="ok", tool_call_id="x"))
    assert gated.status == "error"
    assert "rejected" in gated.content

    rate_limiter.error = RuntimeError("too many")

    def async_ok(req):
        return ToolMessage(content="ok", tool_call_id="x")

    limited = await middleware.awrap_tool_call(request("parse_netflow"), async_ok)
    assert limited.status == "error"
    middleware.monitor.log_security_event.assert_called()

    rate_limiter.error = None
    from cys_core.domain.security.risk import RiskLevel

    monkeypatch.setattr(security_middleware, "classify_tool_risk_pure", lambda _name, _policy=None: RiskLevel.LOW)

    async def async_handler(req):
        return ToolMessage(content="async-ok", tool_call_id=req.tool_call["id"])

    handled = await middleware.awrap_tool_call(request("parse_netflow"), async_handler)
    assert handled.content == "async-ok"
    middleware.monitor.log_tool_call.assert_called()

    with pytest.raises(ValueError, match="async failed"):
        await middleware.awrap_tool_call(
            request("parse_netflow"),
            lambda _req: (_ for _ in ()).throw(ValueError("async failed")),
        )


def _gateway_hitl_result(*, tool_call_id: str = "call-1", approval_token: str = "tok-abc") -> ToolMessage:
    from cys_core.registry.mcp_tools import HITL_MARKER_KEY

    return ToolMessage(
        content=json.dumps(
            {
                HITL_MARKER_KEY: True,
                "tool_name": "run_active_scan",
                "risk_level": "high",
                "approval_token": approval_token,
            }
        ),
        tool_call_id=tool_call_id,
    )


def _gateway_hitl_middleware(monkeypatch, *, decision: dict, stage: str = "prod"):
    import cys_core.middleware.security_middleware as security_middleware

    middleware = security_middleware.SecurityMiddleware("redteam", "session-1", policy_port=fake_policy_port())
    middleware.rate_limiter = SimpleNamespace(check=MagicMock())
    middleware.monitor = SimpleNamespace(log_security_event=MagicMock(), log_tool_call=MagicMock())
    middleware.stage = stage
    middleware._await_hitl_if_needed = lambda _req: None
    monkeypatch.setattr(security_middleware, "register_hitl_pause", lambda preview: None)
    monkeypatch.setattr(security_middleware, "interrupt", lambda preview: decision)
    return middleware


@pytest.mark.unit
def test_wrap_tool_call_retries_with_approval_token_after_gateway_hitl_approved(monkeypatch):
    """docs/MSP_BACKLOG.md §35/§58 second half: tool-gateway's own hitl_required refusal,
    discovered only after handler(request) returns, must pause for approval and — once
    approved — retry with the approval_token attached so the gateway's anti-tampering check
    (bound to this exact tool_name+args) can verify and let it through."""
    from cys_core.registry.mcp_tools import _pending_approval_token

    middleware = _gateway_hitl_middleware(monkeypatch, decision={"decision": "approve"})
    seen_tokens = []

    def handler(req):
        seen_tokens.append(_pending_approval_token.get(""))
        if len(seen_tokens) == 1:
            return _gateway_hitl_result()
        return ToolMessage(content="scan complete", tool_call_id="call-1")

    result = middleware.wrap_tool_call(request("run_active_scan", args={"target": "lab"}), handler)
    assert seen_tokens == ["", "tok-abc"]
    assert result.content == "scan complete"
    assert _pending_approval_token.get("") == ""


@pytest.mark.unit
def test_wrap_tool_call_fails_closed_when_human_rejects_gateway_hitl(monkeypatch):
    middleware = _gateway_hitl_middleware(monkeypatch, decision={"decision": "reject"})
    calls = {"n": 0}

    def handler(req):
        calls["n"] += 1
        return _gateway_hitl_result()

    result = middleware.wrap_tool_call(request("run_active_scan"), handler)
    assert result.status == "error"
    assert "rejected by human reviewer" in result.content
    assert calls["n"] == 1  # never retried


@pytest.mark.unit
def test_wrap_tool_call_fails_closed_when_approved_retry_is_refused_again(monkeypatch):
    """An approval_token retry that the gateway still refuses (expired/tampered/args changed)
    must not loop or get silently treated as success."""
    middleware = _gateway_hitl_middleware(monkeypatch, decision={"decision": "approve"})

    def handler(req):
        return _gateway_hitl_result()

    result = middleware.wrap_tool_call(request("run_active_scan"), handler)
    assert result.status == "error"
    assert "refused by the gateway" in result.content


@pytest.mark.unit
def test_wrap_tool_call_dev_stage_fails_closed_without_calling_interrupt(monkeypatch):
    middleware = _gateway_hitl_middleware(monkeypatch, decision={"decision": "approve"}, stage="dev")
    interrupt_calls = {"n": 0}

    import cys_core.middleware.security_middleware as security_middleware

    def counting_interrupt(preview):
        interrupt_calls["n"] += 1
        return {"decision": "approve"}

    monkeypatch.setattr(security_middleware, "interrupt", counting_interrupt)

    result = middleware.wrap_tool_call(request("run_active_scan"), lambda req: _gateway_hitl_result())
    assert result.status == "error"
    assert interrupt_calls["n"] == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_awrap_tool_call_retries_with_approval_token_after_gateway_hitl_approved(monkeypatch):
    from cys_core.registry.mcp_tools import _pending_approval_token

    middleware = _gateway_hitl_middleware(monkeypatch, decision={"decision": "approve"})
    middleware.rate_limiter = _AsyncNoop()
    seen_tokens = []

    async def handler(req):
        seen_tokens.append(_pending_approval_token.get(""))
        if len(seen_tokens) == 1:
            return _gateway_hitl_result()
        return ToolMessage(content="scan complete", tool_call_id="call-1")

    result = await middleware.awrap_tool_call(request("run_active_scan", args={"target": "lab"}), handler)
    assert seen_tokens == ["", "tok-abc"]
    assert result.content == "scan complete"


class _AsyncNoop:
    async def acheck(self, _key):
        return None
