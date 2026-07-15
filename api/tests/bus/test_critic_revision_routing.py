from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from cys_core.infrastructure.bus_transport import DELIVERY_TOPIC, InMemoryBusTransport, reset_bus_transport_cache


@pytest.mark.unit
@pytest.mark.asyncio
async def test_critic_revision_routes_to_queue(monkeypatch):
    reset_bus_transport_cache()
    transport = InMemoryBusTransport()
    monkeypatch.setattr("interfaces.control_plane.critic_service.get_bus_transport", lambda: transport)

    enqueued: list[dict] = []

    async def _enqueue(envelope: dict) -> str:
        enqueued.append(envelope)
        return "job-revision-1"

    from cys_core.application.bus_ingress_router import BusIngressRouter

    router = BusIngressRouter(orchestration_enqueue=_enqueue)
    transport.subscribe(DELIVERY_TOPIC, router.route_envelope)

    mock_critic = MagicMock()
    mock_critic.execute.return_value = {"passed": False, "reason": "low_quality"}
    mock_bus = MagicMock()
    mock_bus.send_message.return_value = {
        "recipient": "soc",
        "type": "revision",
        "payload": {"feedback": "critic_revision_requested"},
        "signature": "sig-rev-1",
    }

    with (
        patch(
            "cys_core.application.use_cases.process_finding_critic.ProcessFindingCritic",
            return_value=mock_critic,
        ),
        patch("interfaces.control_plane.critic_service.build_agent_bus", return_value=mock_bus),
        patch(
            "interfaces.control_plane.critic_service.get_container",
            lambda: MagicMock(get_engagement_egress=lambda: MagicMock()),
        ),
    ):
        from interfaces.control_plane.critic_service import CriticService

        service = CriticService()
        finding_envelope = {
            "recipient": "critic",
            "type": "finding",
            "sender": "soc",
            "payload": {
                "event_id": "evt-1",
                "correlation_id": "eng-1",
                "tenant_id": "default",
                "data": {"summary": "bad finding"},
            },
            "signature": "sig-critic-1",
        }
        await service.handle_message(finding_envelope)

    assert len(transport.messages) >= 1
    revision = transport.messages[-1]
    assert revision.get("type") == "revision"
    await transport.publish(DELIVERY_TOPIC, revision)
    assert len(enqueued) == 1
    assert enqueued[0]["recipient"] == "soc"
