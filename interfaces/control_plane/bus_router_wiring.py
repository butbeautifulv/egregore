from __future__ import annotations

from typing import TYPE_CHECKING

from cys_core.application.bus_ingress_router import BusIngressRouter
from cys_core.application.bus_engagement import normalize_correlation_id

if TYPE_CHECKING:
    from bootstrap.container import Container


def build_bus_ingress_router(container: Container) -> BusIngressRouter:
    from interfaces.control_plane.critic_handler import CriticHandler
    from interfaces.control_plane.coordinator_handler import CoordinatorHandler

    critic = CriticHandler()
    coordinator = CoordinatorHandler()
    orchestration = container.get_orchestration_port()

    async def _enqueue_from_bus(envelope: dict) -> str:
        return await orchestration.enqueue_from_bus(envelope)

    def _egress_publish(envelope: dict) -> None:
        payload = envelope.get("payload", {})
        if not isinstance(payload, dict):
            payload = {}
        engagement_id = normalize_correlation_id(
            str(payload.get("correlation_id", payload.get("event_id", ""))),
            payload,
        )
        if engagement_id:
            container.get_engagement_egress().publish_event(
                engagement_id,
                str(envelope.get("type", "control")),
                payload,
            )

    return BusIngressRouter(
        control_handlers={
            "critic": critic.handle,
            "coordinator": coordinator.handle,
        },
        orchestration_enqueue=_enqueue_from_bus,
        egress_publish=_egress_publish,
        dedup_store=container.get_bus_dedup_store(),
        bus_guard=container.get_engagement_bus_guard(),
        metrics=container.get_metrics_port(),
    )
