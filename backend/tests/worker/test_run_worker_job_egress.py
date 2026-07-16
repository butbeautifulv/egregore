from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cys_core.domain.engagement.models import Engagement, EngagementMode, EngagementStatus, PlanStrategy
from cys_core.domain.workers.models import WorkerJob
from cys_core.infrastructure.engagement.memory_store import MemoryEngagementStateStore


@pytest.mark.unit
def test_run_worker_job_egress_only_no_notifier() -> None:
    from tests.application.workers.factory import build_run_worker_job_for_tests

    store = MemoryEngagementStateStore()
    store.upsert(
        Engagement(
            id="evt-1",
            tenant_id="default",
            goal="investigate",
            mode=EngagementMode.ASYNC,
            status=EngagementStatus.RUNNING,
            planner_plan=["consultant"],
            plan_strategy=PlanStrategy.META_LLM,
        )
    )
    egress = MagicMock()
    job = WorkerJob(
        job_id="consultant-evt-1-abc",
        event_id="evt-1",
        persona="consultant",
        correlation_id="evt-1",
    )
    runner = build_run_worker_job_for_tests(
        engagement_store=store,
        engagement_egress=egress,
    )
    assert not hasattr(runner, "investigation_status_notifier")
    runner._mark_persona_completed(job)
    egress.publish_status.assert_called_once()
