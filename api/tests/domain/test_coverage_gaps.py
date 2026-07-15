from __future__ import annotations

import pytest

from cys_core.domain.agents.models import AgentDefinition
from cys_core.domain.security.agent_bus import AgentTrustLevel, SecureAgentBus
from cys_core.domain.security.auth_models import (
    AuthClaims,
    AuthError,
    claims_from_payload,
    extract_roles,
)
from cys_core.domain.security.exceptions import SecurityViolation
from cys_core.domain.security.factory import get_input_sanitizer, get_output_guardrails
from cys_core.domain.security.guardrails import OutputGuardrails
from cys_core.domain.security.prompt_context import format_system_prompt
from cys_core.domain.security.redaction import RedactionService
from cys_core.domain.security.sanitizer import FUZZY_KEYWORDS, InputSanitizer, InjectionVerdict
from cys_core.domain.security.scope import ScopePolicy
from cys_core.domain.workers.job_budget import JobBudgetTracker


@pytest.mark.unit
def test_format_system_prompt_adds_global_rules_prefix():
    text = format_system_prompt("persona", "always be helpful", "SECURITY_RULES:\n1. rule")
    assert "GLOBAL_RULES:\nalways be helpful" in text


@pytest.mark.unit
def test_redact_sensitive_keys_handles_lists():
    service = RedactionService()
    result = service.redact_sensitive_keys([{"api_key": "x"}, {"ok": 1}])
    assert result[0]["api_key"] == "***REDACTED***"
    assert result[1]["ok"] == 1


@pytest.mark.unit
def test_scope_check_tool_call_returns_tool_denial_first():
    policy = ScopePolicy.from_tools({"read_file"})
    reason = policy.check_tool_call("execute_command", {"file_path": "/safe/path"})
    assert reason is not None
    assert "execute_command" in reason


@pytest.mark.unit
def test_job_budget_tracker_get_and_clear():
    JobBudgetTracker.clear_all()
    assert JobBudgetTracker.get("missing") is None
    JobBudgetTracker.configure("s1", max_tokens=10, max_cost_usd=1.0, max_tool_calls=2)
    assert JobBudgetTracker.get("s1") is not None
    JobBudgetTracker.clear("s1")
    assert JobBudgetTracker.get("s1") is None


@pytest.mark.unit
def test_auth_claims_has_any_role_empty_required():
    claims = AuthClaims(sub="u1", roles=("egregore-reader",))
    assert claims.has_any_role() is True


@pytest.mark.unit
def test_extract_roles_ignores_non_list_roles():
    roles = extract_roles({"realm_access": {"roles": "not-a-list"}}, "client")
    assert roles == ()


@pytest.mark.unit
def test_extract_roles_merges_realm_and_client_roles():
    claims = {
        "realm_access": {"roles": ["egregore-reader", ""]},
        "resource_access": {"egregore": {"roles": ["egregore-operator", "egregore-reader"]}},
    }
    roles = extract_roles(claims, "egregore")
    assert roles == ("egregore-reader", "egregore-operator")


@pytest.mark.unit
def test_auth_claims_has_any_role_match():
    claims = AuthClaims(sub="u1", roles=("egregore-reader",))
    assert claims.has_any_role("egregore-operator") is False
    assert claims.has_any_role("egregore-reader") is True


@pytest.mark.unit
def test_claims_from_payload_requires_subject():
    with pytest.raises(AuthError, match="missing subject"):
        claims_from_payload({}, client_id="egregore")
    claims = claims_from_payload({"sub": "user-1", "email": 123}, client_id="egregore")
    assert claims.sub == "user-1"
    assert claims.email == ""


@pytest.mark.unit
def test_security_factory_singletons():
    assert get_input_sanitizer() is get_input_sanitizer()
    assert get_output_guardrails() is get_output_guardrails()
    assert isinstance(get_output_guardrails(), OutputGuardrails)


@pytest.mark.unit
def test_agent_definition_allowed_tools():
    agent = AgentDefinition(
        name="n",
        description="d",
        role="worker",
        system_prompt="p",
        tools=["a", "b"],
    )
    assert agent.allowed_tools == {"a", "b"}


@pytest.mark.unit
def test_agent_bus_blocks_escalation_only_path_without_approval():
    bus = SecureAgentBus(signing_key=b"key")
    bus.register_agent("soc", AgentTrustLevel.INTERNAL, ["redteam"])
    bus.register_agent("redteam", AgentTrustLevel.PRIVILEGED, [])
    with pytest.raises(SecurityViolation, match="critic-approved escalation"):
        bus.send_message("soc", "redteam", "finding", {})
    assert bus.security_events[-1]["type"] == "blocked_privileged_escalation_path"


@pytest.mark.unit
def test_guardrails_detects_prompt_leakage_in_response():
    guardrails = OutputGuardrails()
    with pytest.raises(SecurityViolation, match="prompt leakage"):
        guardrails.validate_output({"response": "SYSTEM_INSTRUCTIONS:\nsecret"})


@pytest.mark.unit
def test_sanitizer_fuzzy_match_on_typo_keyword():
    keyword = next(iter(FUZZY_KEYWORDS))
    typo = keyword[:-1] + ("x" if keyword[-1] != "x" else "y")
    sanitizer = InputSanitizer()
    assert sanitizer.classify(f"please {typo} now") is InjectionVerdict.SOFT
