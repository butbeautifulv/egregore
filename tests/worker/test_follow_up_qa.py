from __future__ import annotations

import json

import pytest

from cys_core.application.workers.follow_up_publisher import extract_follow_up_answer
from cys_core.domain.findings.quality_gates import (
    coerce_consultant_advisory_result,
    consultant_finding_gaps,
    follow_up_answer_gaps,
)
from cys_core.domain.follow_up.models import is_follow_up_orchestrator, work_kind_from_payload


@pytest.mark.unit
def test_follow_up_answer_gaps_requires_text() -> None:
    assert follow_up_answer_gaps({}) == ["missing_answer"]
    assert follow_up_answer_gaps({"answer": "ok"}) == []


@pytest.mark.unit
def test_extract_follow_up_answer_prefers_answer_field() -> None:
    assert extract_follow_up_answer({"answer": " timeline "}) == "timeline"


@pytest.mark.unit
def test_extract_follow_up_answer_uses_summary_when_only_structured_key() -> None:
    text = extract_follow_up_answer({"summary": "fallback"})
    parsed = json.loads(text)
    assert parsed["summary"] == "fallback"


@pytest.mark.unit
def test_extract_follow_up_answer_prefers_structured_over_plain_answer() -> None:
    result = {
        "answer": "short prose",
        "topic": "Network hardening",
        "summary": "Short summary",
    }
    text = extract_follow_up_answer(result)
    parsed = json.loads(text)
    assert parsed["topic"] == "Network hardening"


@pytest.mark.unit
def test_prepare_follow_up_result_coerces_consultant_qa() -> None:
    from cys_core.application.workers.follow_up_publisher import prepare_follow_up_result
    from cys_core.domain.workers.models import WorkerJob

    job = WorkerJob(
        job_id="consultant-fu-1",
        event_id="e1",
        persona="consultant",
        correlation_id="wo-1",
        tenant_id="default",
        payload={"work_kind": "follow_up_qa", "operator_message": "Explain risk"},
    )
    result = {"raw": "Advisory prose about the incident."}
    prepared = prepare_follow_up_result(job, result)
    assert consultant_finding_gaps(prepared) == []


@pytest.mark.unit
def test_extract_follow_up_answer_serializes_structured_finding() -> None:
    result = {
        "topic": "Network hardening",
        "summary": "Short summary",
        "recommendations": ["Segment VLANs", "Enable MFA"],
        "confidence": 0.8,
    }
    text = extract_follow_up_answer(result)
    parsed = json.loads(text)
    assert parsed["topic"] == "Network hardening"
    assert parsed["recommendations"] == ["Segment VLANs", "Enable MFA"]


@pytest.mark.unit
def test_coerce_consultant_advisory_result_from_plain_text() -> None:
    result = {"raw": "Привет, я консультант по безопасности."}
    assert coerce_consultant_advisory_result(result, goal="Как дела?") is True
    assert consultant_finding_gaps(result) == []


@pytest.mark.unit
def test_coerce_consultant_advisory_result_skips_when_no_text() -> None:
    result: dict[str, str] = {}
    assert coerce_consultant_advisory_result(result, goal="test") is False


@pytest.mark.unit
def test_follow_up_work_kind_helpers() -> None:
    payload = {"phase": "follow_up", "work_kind": "follow_up_qa"}
    assert work_kind_from_payload(payload) == "follow_up_qa"
    assert is_follow_up_orchestrator(payload) is True
