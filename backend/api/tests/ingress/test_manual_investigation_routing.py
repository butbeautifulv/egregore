from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from cys_core.application.routing.event_router import EventRouter
from cys_core.application.use_cases.engagement_planner import ASYNC_PLANNER_PENDING
from cys_core.application.use_cases.route_and_enqueue import RouteAndEnqueueEvent
from cys_core.application.use_cases.start_engagement import StartEngagement
from cys_core.domain.engagement.models import EngagementRequest, EngagementStatus, PlanStrategy
from cys_core.domain.engagement.planner_job import ENGAGEMENT_PLAN_WORK_KIND, ENGAGEMENT_PLANNER_PERSONA
from cys_core.infrastructure.engagement.memory_store import MemoryEngagementStateStore
from tests.application.port_fakes import fake_correlation_id_port
from tests.conftest import default_policy_port


@pytest.mark.unit
@pytest.mark.asyncio
async def test_meta_llm_engagement_enqueues_planner_job_not_in_process() -> None:
    """api must never construct a MetaPlanner — it enqueues a WorkerJob(persona="planner",
    work_kind="engagement_plan") and returns immediately. See
    docs/MICROSERVICES_SPLIT_PLAN.md §0/§1.2 — the real planner (with the real agent
    runtime) lives in worker's EngagementPlannerRunner now, not here.
    """
    eng_store = MemoryEngagementStateStore()
    enqueued: list[tuple[str, list[str], dict]] = []

    class Enqueuer:
        async def enqueue_from_routing(self, event_id, personas, **kwargs):
            enqueued.append((event_id, personas, kwargs))
            return [f"job-{persona}" for persona in personas]

    dispatch = MagicMock(enqueuer=Enqueuer(), dispatch_async=AsyncMock())
    start = StartEngagement(engagement_store=eng_store, dispatch=dispatch, egress=MagicMock())
    request = EngagementRequest(
        goal="Investigate beaconing",
        plan_strategy=PlanStrategy.META_LLM,
        correlation_id="inv-manual",
    )

    engagement, decision, job_ids = await start.execute(request)

    assert decision.reason == ASYNC_PLANNER_PENDING
    assert decision.personas == []
    assert job_ids == []
    assert engagement.status == EngagementStatus.PLANNING
    assert engagement.planner_status == "planning"

    assert len(enqueued) == 1
    event_id, personas, kwargs = enqueued[0]
    assert personas == [ENGAGEMENT_PLANNER_PERSONA]
    assert kwargs["payload"]["work_kind"] == ENGAGEMENT_PLAN_WORK_KIND
    assert kwargs["payload"]["goal"] == "Investigate beaconing"

    stored = eng_store.get("default", "inv-manual")
    assert stored is not None
    assert stored.planner_status == "planning"


@pytest.mark.unit
def test_siem_alert_still_uses_yaml_router():
    from cys_core.registry.product_context import default_agents_root

    router = EventRouter.from_plans_dir(
        default_agents_root() / "plans",
        policy_port=default_policy_port(),
    )

    class Enqueuer:
        def enqueue_from_routing_sync(self, event_id, personas, **kwargs):
            return [f"job-{persona}" for persona in personas]

        async def enqueue_from_routing(self, event_id, personas, **kwargs):
            return [f"job-{persona}" for persona in personas]

    use_case = RouteAndEnqueueEvent(
        router=router,
        enqueuer=Enqueuer(),
        correlation_id_port=fake_correlation_id_port(),
    )
    event, decision, job_ids = use_case.execute("siem.alert", {"alert": "test"}, severity="high")
    assert decision.reason != "llm_planner"
    assert "soc" in decision.personas
    assert job_ids
