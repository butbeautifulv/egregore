from __future__ import annotations

from cys_core.application.guardrails.policy_gate import check_policy_fail_closed


def test_policy_fail_closed_when_missing() -> None:
    d = check_policy_fail_closed(policy_loaded=False, tool_name="search")
    assert not d.allowed
    assert "fail_closed" in d.reason


def test_policy_allows_when_loaded() -> None:
    d = check_policy_fail_closed(policy_loaded=True, tool_name="search")
    assert d.allowed
