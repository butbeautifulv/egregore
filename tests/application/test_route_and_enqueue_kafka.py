from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from cys_core.application.use_cases.route_and_enqueue import RouteAndEnqueueEvent
from cys_core.domain.events.models import RoutingDecision


@pytest.mark.unit
@pytest.mark.asyncio
async def test_kafka_bypass_for_sync_advisory_investigation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MANUAL_INVESTIGATION_ASYNC", "true")
    from bootstrap.settings import get_settings

    get_settings.cache_clear()

    publish = AsyncMock(return_value=True)
    router = MagicMock()
    router.route.return_value = RoutingDecision(
        event_id="evt-x",
        personas=["soc"],
        playbook_id="full-assessment",
        reason="matched_1_rules",
    )
    enqueuer = MagicMock()
    enqueuer.enqueue_from_routing = AsyncMock(return_value=["consultant-evt-x-abc"])
    plan = MagicMock()
    plan.to_worker_jobs_payload.return_value = {"planner_plan": ["consultant"]}
    plan.execute = AsyncMock(
        return_value=MagicMock(
            personas=["consultant"],
            depends_on={},
            rationale="advisory_fast_path_consultant_only",
        )
    )

    route = RouteAndEnqueueEvent(
        router=router,
        enqueuer=enqueuer,
        use_kafka=True,
        publish_raw_event=publish,
        plan_investigation=plan,
    )

    _event, decision, job_ids = await route.aexecute(
        "manual.investigation",
        {"goal": "Как защитить Active Directory?"},
    )

    publish.assert_not_awaited()
    router.route.assert_not_called()
    assert decision.reason == "llm_planner"
    assert job_ids == ["consultant-evt-x-abc"]
