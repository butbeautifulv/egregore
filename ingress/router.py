from __future__ import annotations

import uuid
from functools import lru_cache
from typing import Any

from config import settings
from cys_core.domain.events.models import RoutingDecision, SecurityEvent
from cys_core.domain.events.router import EventRouter
from cys_core.registry.product_context import default_agents_root
from workers.orchestrator import WorkerOrchestrator

RAW_TOPIC = "security.events.raw"


async def _publish_raw_event(event: SecurityEvent, bootstrap_servers: str) -> None:
    """Publish SecurityEvent to security.events.raw Kafka topic."""
    try:
        from aiokafka import AIOKafkaProducer
        producer = AIOKafkaProducer(bootstrap_servers=bootstrap_servers)
        await producer.start()
        try:
            payload = event.model_dump_json().encode()
            await producer.send_and_wait(RAW_TOPIC, payload)
        finally:
            await producer.stop()
    except Exception as exc:
        import structlog
        structlog.get_logger(__name__).error(
            "event_ingress.publish_failed", event_id=event.id, error=str(exc)
        )


class EventIngress:
    """Accept structured events, route to workers, enqueue jobs."""

    def __init__(
        self,
        router: EventRouter | None = None,
        orchestrator: WorkerOrchestrator | None = None,
    ) -> None:
        self.router = router or EventRouter.from_plans_dir(default_agents_root() / "plans")
        self.orchestrator = orchestrator or WorkerOrchestrator()

    def ingest(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        severity: str = "medium",
        source: str = "",
        event_id: str | None = None,
        correlation_id: str = "",
    ) -> tuple[SecurityEvent, RoutingDecision, list[str]]:
        event = SecurityEvent(
            id=event_id or f"evt-{uuid.uuid4().hex[:12]}",
            type=event_type,  # type: ignore[arg-type]
            source=source,
            severity=severity,  # type: ignore[arg-type]
            payload=payload,
            correlation_id=correlation_id or "",
        )
        decision = self.router.route(event)
        job_ids: list[str] = []
        if decision.personas:
            job_ids = self.orchestrator.enqueue_from_routing_sync(
                event.id,
                decision.personas,
                playbook_id=decision.playbook_id,
                payload=payload,
                correlation_id=event.correlation_id or event.id,
            )
        return event, decision, job_ids

    async def aingest(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        severity: str = "medium",
        source: str = "",
        event_id: str | None = None,
        correlation_id: str = "",
    ) -> tuple[SecurityEvent, RoutingDecision, list[str]]:
        event = SecurityEvent(
            id=event_id or f"evt-{uuid.uuid4().hex[:12]}",
            type=event_type,  # type: ignore[arg-type]
            source=source,
            severity=severity,  # type: ignore[arg-type]
            payload=payload,
            correlation_id=correlation_id or "",
        )

        if settings.use_kafka:
            await _publish_raw_event(event, settings.kafka_bootstrap_servers)
            return event, RoutingDecision(event_id=event.id), []

        # Redis / memory path (existing behavior)
        decision = self.router.route(event)
        job_ids: list[str] = []
        if decision.personas:
            job_ids = await self.orchestrator.enqueue_from_routing(
                event.id,
                decision.personas,
                playbook_id=decision.playbook_id,
                payload=payload,
                correlation_id=event.correlation_id or event.id,
            )
        return event, decision, job_ids


@lru_cache
def get_event_ingress() -> EventIngress:
    return EventIngress()
