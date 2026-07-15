from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from cys_core.application.use_cases.route_and_enqueue import RouteAndEnqueueEvent
from cys_core.domain.events.models import RoutingDecision
from tests.application.port_fakes import fake_correlation_id_port


@pytest.mark.unit
@pytest.mark.asyncio
async def test_kafka_publish_skips_local_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    publish = AsyncMock(return_value=True)
    router = MagicMock()
    router.route.return_value = RoutingDecision(
        event_id="evt-x",
        personas=["soc"],
        playbook_id="incident-triage",
        reason="matched_1_rules",
    )
    enqueuer = MagicMock()
    enqueuer.enqueue_from_routing = AsyncMock(return_value=["soc-evt-x-abc"])

    route = RouteAndEnqueueEvent(
        router=router,
        enqueuer=enqueuer,
        correlation_id_port=fake_correlation_id_port(),
        use_kafka=True,
        publish_raw_event=publish,
    )

    _event, decision, job_ids = await route.aexecute(
        "siem.alert",
        {"alert_id": "a-1"},
    )

    publish.assert_awaited_once()
    router.route.assert_called_once()
    enqueuer.enqueue_from_routing.assert_not_awaited()
    assert job_ids == []
    assert decision.personas == ["soc"]
