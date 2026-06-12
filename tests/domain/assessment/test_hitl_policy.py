import pytest

from cys_core.domain.assessment.services import HitlPolicy


@pytest.mark.unit
def test_hitl_policy_preview_shape():
    policy = HitlPolicy()
    preview = policy.preview(0.5, [{"data": {"severity": "high"}}])
    assert preview["trust_score"] == 0.5
    assert preview["findings_count"] == 1
    assert len(preview["high_severity"]) == 1
    assert "message" in preview


@pytest.mark.unit
def test_hitl_policy_auto_approves_low_risk():
    policy = HitlPolicy()
    decision = policy.decide(
        critic_result={"trust_score": 0.95},
        findings=[{"data": {"severity": "low"}}],
        trust_score_threshold=0.7,
        stage="prod",
        auto_approve_threshold="low",
    )
    assert decision.approved is True
    assert decision.pending_approval is None


@pytest.mark.unit
def test_hitl_policy_manual_decision_bool():
    policy = HitlPolicy()
    decision = policy.decide(
        critic_result={"trust_score": 0.2},
        findings=[{"data": {"severity": "critical"}}],
        trust_score_threshold=0.9,
        stage="prod",
        auto_approve_threshold="low",
        manual_decision=True,
    )
    assert decision.approved is True


@pytest.mark.unit
def test_hitl_policy_manual_decision_dict():
    policy = HitlPolicy()
    decision = policy.decide(
        critic_result={"trust_score": 0.2},
        findings=[{"data": {"severity": "critical"}}],
        trust_score_threshold=0.9,
        stage="prod",
        auto_approve_threshold="low",
        manual_decision={"approved": True},
    )
    assert decision.approved is True
