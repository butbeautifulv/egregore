from __future__ import annotations

from cys_core.domain.engagement.models import EngagementMode, EngagementRequest, EngagementStatus, PlanStrategy


def test_engagement_request_defaults():
    req = EngagementRequest(goal="test goal")
    assert req.profile_id == "cybersec-soc"
    assert req.mode == EngagementMode.ASYNC
    assert req.plan_strategy == PlanStrategy.DECLARATIVE


def test_engagement_status_values():
    assert EngagementStatus.CREATED.value == "created"
    assert EngagementStatus.ENQUEUED.value == "enqueued"
