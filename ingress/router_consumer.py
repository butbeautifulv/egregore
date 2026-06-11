from __future__ import annotations

import asyncio
import json
import signal
import uuid
from typing import Any

import structlog

from config import settings
from cys_core.domain.events.models import SecurityEvent
from cys_core.domain.events.router import EventRouter
from cys_core.domain.workers.models import WorkerJob
from cys_core.infrastructure.kafka_queue import KafkaJobQueue
from cys_core.registry.product_context import default_agents_root

logger = structlog.get_logger(__name__)

RAW_TOPIC = "security.events.raw"


class RouterConsumer:
    """Consumes security.events.raw, routes events, publishes worker jobs."""

    def __init__(
        self,
        *,
        router: EventRouter | None = None,
        bootstrap_servers: str | None = None,
        consumer_group: str | None = None,
    ) -> None:
        self.router = router or EventRouter.from_plans_dir(default_agents_root() / "plans")
        self._bootstrap = bootstrap_servers or settings.kafka_bootstrap_servers
        self._group = consumer_group or f"{settings.kafka_consumer_group_prefix}-router"
        self._stop_event = asyncio.Event()
        self._events_routed = 0

    def _setup_signals(self) -> None:
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._stop_event.set)

    def _make_job(self, event: SecurityEvent, persona: str, playbook_id: str) -> dict[str, Any]:
        job_id = f"{persona}-{event.id}-{uuid.uuid4().hex[:8]}"
        job = WorkerJob(
            job_id=job_id,
            event_id=event.id,
            persona=persona,
            playbook_id=playbook_id,
            payload=event.payload,
            correlation_id=event.correlation_id or event.id,
        )
        return job.model_dump()

    async def _publish_jobs(self, event: SecurityEvent, personas: list[str], playbook_id: str) -> list[str]:
        queue = KafkaJobQueue(bootstrap_servers=self._bootstrap)
        job_ids: list[str] = []
        for persona in personas:
            job = self._make_job(event, persona, playbook_id)
            jid = await queue.aenqueue(job)
            job_ids.append(jid)
        return job_ids

    async def _process_message(self, raw: bytes) -> None:
        try:
            data = json.loads(raw.decode())
            event = SecurityEvent.model_validate(data)
        except Exception as exc:
            logger.warning("router_consumer.parse_error", error=str(exc))
            return

        try:
            decision = self.router.route(event)
        except Exception as exc:
            logger.warning("router_consumer.route_error", event_id=event.id, error=str(exc))
            return

        if not decision.personas:
            logger.debug("router_consumer.no_route", event_id=event.id, event_type=event.type)
            return

        try:
            job_ids = await self._publish_jobs(event, decision.personas, decision.playbook_id)
            self._events_routed += 1
            logger.info(
                "router_consumer.routed",
                event_id=event.id,
                personas=decision.personas,
                job_ids=job_ids,
            )
        except Exception as exc:
            logger.error("router_consumer.enqueue_error", event_id=event.id, error=str(exc))

    async def run(self) -> int:
        """Run consumer loop. Returns number of events routed."""
        self._setup_signals()
        logger.info("router_consumer.started", topic=RAW_TOPIC, group=self._group)

        try:
            from aiokafka import AIOKafkaConsumer
        except ImportError:
            logger.error("router_consumer.aiokafka_missing")
            return 0

        consumer = AIOKafkaConsumer(
            RAW_TOPIC,
            bootstrap_servers=self._bootstrap,
            group_id=self._group,
            auto_offset_reset="earliest",
            enable_auto_commit=True,
        )

        await consumer.start()
        try:
            while not self._stop_event.is_set():
                try:
                    records = await consumer.getmany(timeout_ms=500, max_records=10)
                    for _tp, msgs in records.items():
                        for msg in msgs:
                            await self._process_message(msg.value)
                except Exception as exc:
                    logger.error("router_consumer.poll_error", error=str(exc))
                    await asyncio.sleep(1)
        finally:
            await consumer.stop()

        logger.info("router_consumer.stopped", events_routed=self._events_routed)
        return self._events_routed


async def run_router_consumer(
    *,
    bootstrap_servers: str | None = None,
    consumer_group: str | None = None,
    router: EventRouter | None = None,
) -> int:
    consumer = RouterConsumer(
        router=router,
        bootstrap_servers=bootstrap_servers,
        consumer_group=consumer_group,
    )
    return await consumer.run()
