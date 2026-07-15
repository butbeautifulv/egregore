"""Abuse case: approval bypass — high-impact findings require HITL."""


def test_high_severity_triggers_hitl(guardrails):
    findings = [{"agent": "redteam", "data": {"severity": "critical", "finding": "RCE"}}]
    assert guardrails.requires_hitl(findings, trust_score=0.9, threshold=0.5)


def test_low_trust_triggers_hitl(guardrails):
    findings = [{"agent": "network", "data": {"severity": "low"}}]
    assert guardrails.requires_hitl(findings, trust_score=0.2, threshold=0.5)


def test_low_severity_high_trust_skips_hitl(guardrails):
    findings = [{"agent": "network", "data": {"severity": "low"}}]
    assert not guardrails.requires_hitl(findings, trust_score=0.9, threshold=0.5)
