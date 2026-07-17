import pytest

from cys_core.domain.assessment.models import AssessmentReport, PendingApproval


@pytest.mark.unit
def test_pending_approval_serialization():
    pending = PendingApproval(trust_score=0.4, findings_count=2, high_severity=[], message="review")
    data = pending.model_dump()
    assert data["trust_score"] == 0.4
    assert data["message"] == "review"


@pytest.mark.unit
def test_assessment_report_exclude_none():
    report = AssessmentReport(status="published", session_id="s1", findings=[])
    data = report.model_dump(exclude_none=True)
    assert data["status"] == "published"
    assert "critic_result" not in data
