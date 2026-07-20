from __future__ import annotations

from types import SimpleNamespace

import pytest

from bootstrap.containers.tools_container import (
    ToolsContainer,
    _resolve_hitl_decision,
    _resolve_sandbox_token_violation,
    _resolve_scope_violation,
)
from cys_core.domain.agents.models import AgentDefinition
from cys_core.domain.catalog.models import ProfilePolicyPayload
from cys_core.domain.security.approval_tokens import mint_approval_token
from cys_core.domain.security.sandbox_tokens import mint_sandbox_token
from cys_core.domain.tools.exceptions import HitlRequired, SandboxTokenInvalid, ScopeViolation
from cys_core.domain.tools.models import ToolInvokeCommand

_SECRET = b"test-signing-key"


def _command(**overrides) -> ToolInvokeCommand:
    base = {
        "tool_name": "run_active_scan",
        "args": {},
        "persona": "soc",
        "sandbox_id": "sb-1",
    }
    base.update(overrides)
    return ToolInvokeCommand(**base)


def _definition(name: str, tools: list[str]) -> AgentDefinition:
    return AgentDefinition(
        name=name,
        description="test",
        role="worker",
        system_prompt="test",
        tools=tools,
    )


class _FakePolicyPort:
    def __init__(self, policy: ProfilePolicyPayload) -> None:
        self._policy = policy

    def get_policy(self, _profile_id: str) -> ProfilePolicyPayload:
        return self._policy

    def get_hitl_threshold(self, _profile_id: str) -> str:
        return self._policy.hitl_auto_approve_threshold


def _container(
    mode: str,
    *,
    sandbox_token_mode: str = "off",
    hitl_mode: str = "off",
    policy: ProfilePolicyPayload | None = None,
) -> ToolsContainer:
    fake_outer = SimpleNamespace(
        settings=SimpleNamespace(
            tool_scope_mode=mode,
            tool_sandbox_token_mode=sandbox_token_mode,
            tool_hitl_mode=hitl_mode,
            bus_signing_key_bytes=_SECRET,
        ),
        get_profile_policy_port=lambda: _FakePolicyPort(policy or ProfilePolicyPayload()),
    )
    return ToolsContainer(fake_outer)  # type: ignore[arg-type]


@pytest.mark.unit
def test_resolve_scope_violation_allows_tool_in_allowlist(monkeypatch):
    registry = type("Registry", (), {"get": lambda self, name: _definition(name, ["run_active_scan"])})()
    monkeypatch.setattr("cys_core.registry.agents.get_agent_registry", lambda: registry)
    assert _resolve_scope_violation(_command(tool_name="run_active_scan")) is None


@pytest.mark.unit
def test_resolve_scope_violation_flags_tool_outside_allowlist(monkeypatch):
    registry = type("Registry", (), {"get": lambda self, name: _definition(name, ["read_repo_metadata"])})()
    monkeypatch.setattr("cys_core.registry.agents.get_agent_registry", lambda: registry)
    assert _resolve_scope_violation(_command(tool_name="run_active_scan")) is not None


@pytest.mark.unit
def test_resolve_scope_violation_fails_open_for_unknown_persona(monkeypatch):
    def _raise_unknown(self, name):
        raise KeyError(f"Unknown agent: {name}")

    registry = type("Registry", (), {"get": _raise_unknown})()
    monkeypatch.setattr("cys_core.registry.agents.get_agent_registry", lambda: registry)
    # Must not raise, must not flag — an unregistered persona in this
    # package's catalog snapshot should not block every tool call for it.
    assert _resolve_scope_violation(_command(persona="unregistered-persona")) is None


@pytest.mark.unit
def test_check_scope_off_mode_never_checks(monkeypatch):
    registry = type("Registry", (), {"get": lambda self, name: _definition(name, [])})()
    monkeypatch.setattr("cys_core.registry.agents.get_agent_registry", lambda: registry)
    container = _container("off")
    container._check_scope(_command(tool_name="run_active_scan"))  # must not raise


@pytest.mark.unit
def test_check_scope_shadow_mode_logs_but_never_raises(monkeypatch):
    registry = type("Registry", (), {"get": lambda self, name: _definition(name, [])})()
    monkeypatch.setattr("cys_core.registry.agents.get_agent_registry", lambda: registry)
    container = _container("shadow")
    container._check_scope(_command(tool_name="run_active_scan"))  # must not raise


@pytest.mark.unit
def test_check_scope_enforce_mode_raises_on_violation(monkeypatch):
    registry = type("Registry", (), {"get": lambda self, name: _definition(name, [])})()
    monkeypatch.setattr("cys_core.registry.agents.get_agent_registry", lambda: registry)
    container = _container("enforce")
    with pytest.raises(ScopeViolation):
        container._check_scope(_command(tool_name="run_active_scan"))


def _token(**overrides) -> str:
    base = {"run_id": "job-1", "persona": "soc", "tenant_id": "default", "job_id": "job-1", "ttl_s": 60.0}
    base.update(overrides)
    return mint_sandbox_token(secret=_SECRET, **base)


@pytest.mark.unit
def test_resolve_sandbox_token_violation_allows_valid_matching_token():
    token = _token()
    command = _command(persona="soc", job_id="job-1", sandbox_token=token)
    assert _resolve_sandbox_token_violation(command, secret=_SECRET) is None


@pytest.mark.unit
def test_resolve_sandbox_token_violation_flags_missing_token():
    command = _command(sandbox_token="")
    assert _resolve_sandbox_token_violation(command, secret=_SECRET) == "missing_sandbox_token"


@pytest.mark.unit
def test_resolve_sandbox_token_violation_flags_bad_signature():
    command = _command(sandbox_token=_token(), job_id="job-1")
    # Verifying with a different secret than it was minted with must fail signature check.
    assert _resolve_sandbox_token_violation(command, secret=b"wrong-secret") == "invalid_or_expired_sandbox_token"


@pytest.mark.unit
def test_resolve_sandbox_token_violation_flags_expired_token():
    token = _token(ttl_s=-1.0)
    command = _command(job_id="job-1", sandbox_token=token)
    assert _resolve_sandbox_token_violation(command, secret=_SECRET) == "invalid_or_expired_sandbox_token"


@pytest.mark.unit
def test_resolve_sandbox_token_violation_flags_job_id_mismatch():
    token = _token(job_id="job-1")
    command = _command(job_id="job-2", sandbox_token=token)
    assert _resolve_sandbox_token_violation(command, secret=_SECRET) == "sandbox_token_job_id_mismatch"


@pytest.mark.unit
def test_resolve_sandbox_token_violation_flags_persona_mismatch():
    token = _token(persona="soc", job_id="job-1")
    command = _command(persona="hunter", job_id="job-1", sandbox_token=token)
    assert _resolve_sandbox_token_violation(command, secret=_SECRET) == "sandbox_token_persona_mismatch"


@pytest.mark.unit
def test_check_sandbox_token_off_mode_never_checks():
    container = _container("off", sandbox_token_mode="off")
    container._check_sandbox_token(_command(sandbox_token=""))  # must not raise


@pytest.mark.unit
def test_check_sandbox_token_shadow_mode_logs_but_never_raises():
    container = _container("off", sandbox_token_mode="shadow")
    container._check_sandbox_token(_command(sandbox_token=""))  # must not raise


@pytest.mark.unit
def test_check_sandbox_token_enforce_mode_raises_on_violation():
    container = _container("off", sandbox_token_mode="enforce")
    with pytest.raises(SandboxTokenInvalid):
        container._check_sandbox_token(_command(sandbox_token=""))


@pytest.mark.unit
def test_check_sandbox_token_enforce_mode_allows_valid_token():
    container = _container("off", sandbox_token_mode="enforce")
    token = _token(persona="soc", job_id="job-1")
    container._check_sandbox_token(_command(persona="soc", job_id="job-1", sandbox_token=token))  # must not raise


def _risky_policy(
    *, tool_name: str = "run_active_scan", risk: str = "high", threshold: str = "low"
) -> ProfilePolicyPayload:
    return ProfilePolicyPayload(tool_risk={tool_name: risk}, hitl_auto_approve_threshold=threshold)


@pytest.mark.unit
def test_resolve_hitl_decision_allows_low_risk_tool_under_threshold():
    policy = ProfilePolicyPayload(tool_risk={"read_repo_metadata": "low"}, hitl_auto_approve_threshold="low")
    command = _command(tool_name="read_repo_metadata")
    assert _resolve_hitl_decision(command, policy_port=_FakePolicyPort(policy), secret=_SECRET) is None


@pytest.mark.unit
def test_resolve_hitl_decision_flags_high_risk_tool_over_threshold():
    policy = _risky_policy()
    command = _command(tool_name="run_active_scan")
    decision = _resolve_hitl_decision(command, policy_port=_FakePolicyPort(policy), secret=_SECRET)
    assert decision is not None
    risk_level, approval_token = decision
    assert risk_level == "high"
    assert approval_token


@pytest.mark.unit
def test_resolve_hitl_decision_bypasses_reclassification_with_a_valid_matching_token():
    policy = _risky_policy()
    args = {"target": "host-a"}
    token = mint_approval_token(tool_name="run_active_scan", tool_args=args, ttl_s=60, secret=_SECRET)
    command = _command(tool_name="run_active_scan", args=args, approval_token=token)
    assert _resolve_hitl_decision(command, policy_port=_FakePolicyPort(policy), secret=_SECRET) is None


@pytest.mark.unit
def test_resolve_hitl_decision_does_not_bypass_when_retry_args_differ_from_the_approved_call():
    """The whole anti-tampering point: a token approved for one set of args must not
    silently approve a substituted, more dangerous set of args on retry."""
    policy = _risky_policy()
    token = mint_approval_token(tool_name="run_active_scan", tool_args={"target": "host-a"}, ttl_s=60, secret=_SECRET)
    command = _command(tool_name="run_active_scan", args={"target": "host-b"}, approval_token=token)
    decision = _resolve_hitl_decision(command, policy_port=_FakePolicyPort(policy), secret=_SECRET)
    assert decision is not None


@pytest.mark.unit
def test_check_hitl_off_mode_never_checks():
    container = _container("off", hitl_mode="off", policy=_risky_policy())
    container._check_hitl(_command(tool_name="run_active_scan"))  # must not raise


@pytest.mark.unit
def test_check_hitl_shadow_mode_logs_but_never_raises():
    container = _container("off", hitl_mode="shadow", policy=_risky_policy())
    container._check_hitl(_command(tool_name="run_active_scan"))  # must not raise


@pytest.mark.unit
def test_check_hitl_enforce_mode_raises_on_high_risk_call():
    container = _container("off", hitl_mode="enforce", policy=_risky_policy())
    with pytest.raises(HitlRequired) as exc_info:
        container._check_hitl(_command(tool_name="run_active_scan"))
    assert exc_info.value.risk_level == "high"
    assert exc_info.value.approval_token


@pytest.mark.unit
def test_check_hitl_enforce_mode_allows_low_risk_call():
    policy = ProfilePolicyPayload(tool_risk={"read_repo_metadata": "low"}, hitl_auto_approve_threshold="low")
    container = _container("off", hitl_mode="enforce", policy=policy)
    container._check_hitl(_command(tool_name="read_repo_metadata"))  # must not raise


@pytest.mark.unit
def test_check_hitl_enforce_mode_allows_valid_approval_token_retry():
    policy = _risky_policy()
    args = {"target": "host-a"}
    token = mint_approval_token(tool_name="run_active_scan", tool_args=args, ttl_s=60, secret=_SECRET)
    container = _container("off", hitl_mode="enforce", policy=policy)
    container._check_hitl(_command(tool_name="run_active_scan", args=args, approval_token=token))  # must not raise
