"""Tests for control plane cleanup (silent critic, profile gate, outcomes)."""

from __future__ import annotations

from cys_core.application.control_plane.critic_display import (
    critic_verdict_visible_to_operator,
    format_critic_operator_message,
)
from cys_core.application.findings.outcome_mapper import finding_to_operator_outcome, synthesis_outcome_from_context
from cys_core.domain.engagement.bus_routing import (
    ControlPlaneMode,
    filter_bus_recipients_for_plan,
    filter_control_plane_recipients,
)


def test_critic_pass_not_visible() -> None:
    assert critic_verdict_visible_to_operator({"passed": True, "trust_score": 0.9}) is False


def test_critic_fail_visible() -> None:
    assert critic_verdict_visible_to_operator({"passed": False, "issues_detected": ["gap"]}) is True


def test_critic_revision_visible() -> None:
    assert critic_verdict_visible_to_operator({"passed": False, "revision_enqueued": True}) is True


def test_format_critic_operator_message() -> None:
    text = format_critic_operator_message(
        {"passed": False, "issues_detected": ["missing evidence"]},
        source_persona="soc",
    )
    assert "soc" in text
    assert "missing evidence" in text


def test_filter_control_plane_off() -> None:
    recipients = filter_control_plane_recipients(["network", "critic", "coordinator"], ControlPlaneMode.OFF)
    assert recipients == ["network"]


def test_filter_control_plane_gate_only() -> None:
    recipients = filter_control_plane_recipients(["network", "critic", "coordinator"], ControlPlaneMode.GATE_ONLY)
    assert recipients == ["network", "critic"]


def test_filter_bus_recipients_respects_mode() -> None:
    recipients = filter_bus_recipients_for_plan(
        ["soc", "critic", "coordinator"],
        ["soc"],
        control_plane_mode=ControlPlaneMode.OFF,
    )
    assert recipients == ["soc"]


def test_finding_to_operator_outcome() -> None:
    outcome = finding_to_operator_outcome(
        {"topic": "Advisory", "summary": "Use MFA", "recommendations": ["Enable MFA"], "confidence": 0.8},
        kind="advisory",
    )
    assert outcome.kind == "advisory"
    assert outcome.summary == "Use MFA"
    assert outcome.recommendations == ["Enable MFA"]


def test_synthesis_outcome_provenance() -> None:
    outcome = synthesis_outcome_from_context(
        {"summary": "Done", "topic": "Investigation"},
        specialist_outcomes=[{"persona": "soc", "job_id": "soc-1", "status": "completed"}],
    )
    assert outcome.kind == "synthesis"
    assert len(outcome.provenance) == 1
    assert outcome.provenance[0].persona == "soc"


def test_append_finding_upserts_same_job() -> None:
    from cys_core.domain.engagement.models import Engagement
    from cys_core.infrastructure.engagement._store_ops import append_finding

    engagement = Engagement(id="eng-1", goal="test")
    append_finding(engagement, {"persona": "soc", "job_id": "soc-1", "finding": {"summary": "v1"}})
    append_finding(engagement, {"persona": "soc", "job_id": "soc-1", "finding": {"summary": "v2"}})
    assert len(engagement.findings_summary) == 1
    assert engagement.findings_summary[0]["finding"]["summary"] == "v2"
