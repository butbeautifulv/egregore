from __future__ import annotations

import pytest


@pytest.mark.unit
def test_domain_layer_exports_and_assessment_services():
    from cys_core.domain.agents import AgentDefinition as DomainAgentDefinition
    from cys_core.domain.agents.models import AgentDefinition
    from cys_core.domain.assessment import AssessmentReportBuilder, HitlPolicy
    from cys_core.domain.findings import CriticResult as DomainCriticResult
    from cys_core.domain.findings.models import CriticResult
    from cys_core.domain.security import OutputGuardrails as DomainGuardrails
    from cys_core.domain.security import SecurityViolation as DomainSecurityViolation
    from cys_core.domain.security.exceptions import SecurityViolation

    assert AgentDefinition is DomainAgentDefinition
    assert CriticResult is DomainCriticResult
    assert SecurityViolation is DomainSecurityViolation

    policy = HitlPolicy(DomainGuardrails())
    assert (
        policy.decide(
            critic_result={"trust_score": 1.0},
            findings=[],
            trust_score_threshold=0.5,
            stage="test",
            auto_approve_threshold="low",
        ).approved
        is True
    )
    auto = policy.decide(
        critic_result={"trust_score": 0.1},
        findings=[],
        trust_score_threshold=0.5,
        stage="dev",
        auto_approve_threshold="medium",
    )
    assert auto.pending_approval == {"auto_approved": True, "reason": "dev stage"}
    pending = policy.decide(
        critic_result={"trust_score": 0.1},
        findings=[{"data": {"severity": "high"}}],
        trust_score_threshold=0.5,
        stage="test",
        auto_approve_threshold="low",
    )
    assert pending.interrupt_preview is not None
    assert pending.interrupt_preview["findings_count"] == 1
    assert (
        policy.decide(
            critic_result={"trust_score": 0.1},
            findings=[],
            trust_score_threshold=0.5,
            stage="test",
            auto_approve_threshold="low",
            manual_decision={"approved": True},
        ).approved
        is True
    )

    builder = AssessmentReportBuilder()
    assert builder.build({"approved": False, "pending_approval": {"reason": "manual"}})["status"] == "rejected"
    assert (
        builder.build({"approved": True, "session_id": "sid", "findings": [], "critic_result": {}, "errors": []})[
            "status"
        ]
        == "published"
    )
