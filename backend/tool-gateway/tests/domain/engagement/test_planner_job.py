from __future__ import annotations

import pytest

from cys_core.domain.engagement.planner_job import (
    ENGAGEMENT_PLAN_WORK_KIND,
    ENGAGEMENT_PLANNER_PERSONA,
    is_engagement_plan_job,
)


@pytest.mark.unit
def test_is_engagement_plan_job_requires_persona_and_work_kind() -> None:
    payload = {"work_kind": ENGAGEMENT_PLAN_WORK_KIND}
    assert is_engagement_plan_job(payload, persona=ENGAGEMENT_PLANNER_PERSONA) is True
    assert is_engagement_plan_job(payload, persona="soc") is False


@pytest.mark.unit
def test_is_engagement_plan_job_false_for_other_work_kinds() -> None:
    assert is_engagement_plan_job({"work_kind": "follow_up_plan"}, persona=ENGAGEMENT_PLANNER_PERSONA) is False
    assert is_engagement_plan_job({}, persona=ENGAGEMENT_PLANNER_PERSONA) is False
