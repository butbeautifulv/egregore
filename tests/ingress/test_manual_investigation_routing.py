from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from cys_core.application.use_cases.plan_investigation import PlanInvestigation
from cys_core.application.use_cases.route_and_enqueue import RouteAndEnqueueEvent
from cys_core.domain.events.router import EventRouter


@pytest.mark.unit
@pytest.mark.asyncio
async def test_manual_investigation_uses_planner_not_yaml_router(monkeypatch):
    monkeypatch.setattr(
        "cys_core.application.use_cases.dispatch_event.settings.manual_investigation_async",
        False,
    )
    enqueued: list[tuple[str, list[str]]] = []

    class Enqueuer:
        async def enqueue_from_routing(self, event_id, personas, **kwargs):
            enqueued.append((event_id, personas))
            return [f"job-{persona}" for persona in personas]

        def enqueue_from_routing_sync(self, event_id, personas, **kwargs):
            enqueued.append((event_id, personas))
            return [f"job-{persona}" for persona in personas]

    planner = PlanInvestigation(
        runtime=SimpleNamespace(
            arun=AsyncMock(
                return_value={
                    "personas": ["soc", "network"],
                    "sub_goals": {"soc": "triage", "network": "beaconing"},
                    "rationale": "test",
                }
            )
        ),
        investigation_store=SimpleNamespace(get=lambda *_a, **_k: None, upsert=lambda *_a, **_k: None),
    )
    use_case = RouteAndEnqueueEvent(
        router=EventRouter(),
        enqueuer=Enqueuer(),
        plan_investigation=planner,
    )

    event, decision, job_ids = await use_case.aexecute(
        "manual.investigation",
        {"goal": "Investigate beaconing"},
        correlation_id="inv-manual",
    )
    assert decision.reason == "llm_planner"
    assert decision.personas == ["soc", "network"]
    assert job_ids == ["job-soc", "job-network"]
    assert event.type == "manual.investigation"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_manual_investigation_async_defers_planner(monkeypatch):
    monkeypatch.setattr(
        "cys_core.application.use_cases.dispatch_event.settings.manual_investigation_async",
        True,
    )
    begun: list[str] = []

    class Enqueuer:
        async def enqueue_from_routing(self, event_id, personas, **kwargs):
            return [f"job-{persona}" for persona in personas]

        def enqueue_from_routing_sync(self, event_id, personas, **kwargs):
            return [f"job-{persona}" for persona in personas]

    class Store:
        def get(self, *_a, **_k):
            return None

        def upsert(self, state):
            begun.append(state.investigation_id)

    planner = PlanInvestigation(
        runtime=SimpleNamespace(arun=AsyncMock()),
        investigation_store=Store(),
    )
    use_case = RouteAndEnqueueEvent(
        router=EventRouter(),
        enqueuer=Enqueuer(),
        plan_investigation=planner,
    )

    event, decision, job_ids = await use_case.aexecute(
        "manual.investigation",
        {"goal": "Investigate beaconing"},
        correlation_id="inv-async",
    )
    from cys_core.application.use_cases.dispatch_event import ASYNC_PLANNER_PENDING

    assert decision.reason == ASYNC_PLANNER_PENDING
    assert decision.personas == []
    assert job_ids == []
    assert begun == ["inv-async"]


@pytest.mark.unit
def test_siem_alert_still_uses_yaml_router():
    from cys_core.registry.product_context import default_agents_root

    router = EventRouter.from_plans_dir(default_agents_root() / "plans")

    class Enqueuer:
        def enqueue_from_routing_sync(self, event_id, personas, **kwargs):
            return [f"job-{persona}" for persona in personas]

        async def enqueue_from_routing(self, event_id, personas, **kwargs):
            return [f"job-{persona}" for persona in personas]

    use_case = RouteAndEnqueueEvent(router=router, enqueuer=Enqueuer())
    event, decision, job_ids = use_case.execute("siem.alert", {"alert": "test"}, severity="high")
    assert decision.reason != "llm_planner"
    assert "soc" in decision.personas
    assert job_ids
