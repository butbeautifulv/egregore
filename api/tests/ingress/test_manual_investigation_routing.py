from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from cys_core.application.use_cases.engagement_planner import ASYNC_PLANNER_PENDING
from tests.application.port_fakes import fake_correlation_id_port, plan_investigation_port_kwargs
from cys_core.application.use_cases.meta_planner import MetaPlanner
from cys_core.application.use_cases.route_and_enqueue import RouteAndEnqueueEvent
from cys_core.application.use_cases.start_engagement import StartEngagement, engagement_request_to_security_event
from cys_core.application.routing.event_router import EventRouter
from tests.conftest import default_policy_port
from cys_core.domain.engagement.models import EngagementMode, EngagementRequest, PlanStrategy
from cys_core.infrastructure.engagement.memory_store import MemoryEngagementStateStore


@pytest.mark.unit
@pytest.mark.asyncio
async def test_meta_llm_engagement_uses_planner_via_start_engagement(monkeypatch):
    import cys_core.application.runtime_config as rc

    monkeypatch.setattr(rc, "_engagement_async_planning", False)
    eng_store = MemoryEngagementStateStore()
    enqueued: list[tuple[str, list[str]]] = []

    class Enqueuer:
        async def enqueue_from_routing(self, event_id, personas, **kwargs):
            enqueued.append((event_id, personas, kwargs))
            return [f"job-{persona}" for persona in personas]

    runtime = SimpleNamespace(
        arun=AsyncMock(
            return_value={
                "personas": ["soc", "network"],
                "sub_goals": {"soc": "triage", "network": "beaconing"},
                "rationale": "test",
            }
        )
    )
    meta = MetaPlanner(
        runtime=runtime,
        engagement_store=eng_store,
        **plan_investigation_port_kwargs(
            resource_source=SimpleNamespace(list_worker_personas=lambda profile_id=None: ["soc", "network"]),
        ),
    )
    dispatch = SimpleNamespace(
        enqueuer=Enqueuer(),
        dispatch_async=AsyncMock(),
    )
    start = StartEngagement(
        engagement_store=eng_store,
        dispatch=dispatch,
        meta_planner=meta,
    )
    request = EngagementRequest(
        goal="Investigate beaconing",
        plan_strategy=PlanStrategy.META_LLM,
        correlation_id="inv-manual",
    )

    engagement, decision, job_ids = await start.execute(request)

    assert decision.reason == "meta_planner"
    assert decision.personas == ["soc", "network"]
    assert job_ids == ["job-soc", "job-network"]

    stored = eng_store.get("default", "inv-manual")
    assert stored is not None
    assert stored.planner_status == "ok"
    assert stored.planner_plan == ["soc", "network"]
    assert stored.planner_rationale == "test"
    assert stored.job_ids == ["job-soc", "job-network"]
    assert engagement.planner_status == "ok"
    assert engagement.planner_plan == ["soc", "network"]
    # get_planner_default_execution_mode() defaults to "parallel" (latency fix — multi-persona
    # investigations dispatch in parallel by default now); _finalize_plan() sets
    # plan.execution_mode=PARALLEL whenever the planner response omits it, so
    # _pipeline_staged() (which requires ExecutionMode.STAGED) is False here.
    assert enqueued[0][2]["pipeline_staged"] is False
    assert enqueued[0][2]["sequential"] is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_meta_llm_async_background_persists_planner_state(monkeypatch):
    import cys_core.application.runtime_config as rc

    monkeypatch.setattr(rc, "_engagement_async_planning", True)
    eng_store = MemoryEngagementStateStore()

    class Enqueuer:
        async def enqueue_from_routing(self, event_id, personas, **kwargs):
            return [f"job-{persona}" for persona in personas]

    runtime = SimpleNamespace(
        arun=AsyncMock(
            return_value={
                "personas": ["consultant"],
                "sub_goals": {"consultant": "advisory"},
                "rationale": "supply chain advisory",
            }
        )
    )
    meta = MetaPlanner(
        runtime=runtime,
        engagement_store=eng_store,
        **plan_investigation_port_kwargs(
            resource_source=SimpleNamespace(list_worker_personas=lambda profile_id=None: ["consultant"]),
        ),
    )
    dispatch = SimpleNamespace(enqueuer=Enqueuer(), dispatch_async=AsyncMock())
    start = StartEngagement(
        engagement_store=eng_store,
        dispatch=dispatch,
        meta_planner=meta,
    )
    request = EngagementRequest(
        goal="Supply chain defense",
        plan_strategy=PlanStrategy.META_LLM,
        correlation_id="inv-async-bg",
    )
    await start.execute(request)
    event = engagement_request_to_security_event(request, request.correlation_id)
    job_ids = await start.plan_async_background(event, dict(event.payload))

    stored = eng_store.get("default", "inv-async-bg")
    assert stored is not None
    assert stored.planner_status == "ok"
    assert stored.planner_plan == ["consultant"]
    assert stored.planner_rationale == "supply chain advisory"
    assert stored.job_ids == ["job-consultant"]
    assert job_ids == ["job-consultant"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_meta_llm_engagement_async_defers_planner(monkeypatch):
    import cys_core.application.runtime_config as rc

    monkeypatch.setattr(rc, "_engagement_async_planning", True)
    eng_store = MemoryEngagementStateStore()
    dispatch = SimpleNamespace(enqueuer=MagicMock(), dispatch_async=AsyncMock())
    meta = MagicMock()
    meta.begin_planning = MagicMock()
    start = StartEngagement(
        engagement_store=eng_store,
        dispatch=dispatch,
        egress=MagicMock(),
        meta_planner=meta,
    )
    request = EngagementRequest(
        goal="Investigate beaconing",
        plan_strategy=PlanStrategy.META_LLM,
        correlation_id="inv-async",
    )
    engagement, decision, job_ids = await start.execute(request)
    assert decision.reason == ASYNC_PLANNER_PENDING
    assert decision.personas == []
    assert job_ids == []
    meta.begin_planning.assert_called_once()


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
