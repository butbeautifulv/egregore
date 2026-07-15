from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any, cast

import structlog

from cys_core.application.bus_engagement import extract_engagement_id
from cys_core.application.bus_fingerprint import envelope_fingerprint
from cys_core.application.engagement_bus_guard import EngagementBusGuard
from cys_core.application.ports.bus_dedup import BusDedupPort
from cys_core.application.ports.bus_ingress_router import BusIngressRouterPort
from cys_core.application.ports.metrics import MetricsPort
from cys_core.domain.security.bus_messages import BusMessageType

logger = structlog.get_logger(__name__)

CONTROL_RECIPIENTS = frozenset({"critic", "coordinator", "egress"})


class BusIngressRouter:
    """Route bus envelopes to control handlers or orchestration enqueue."""

    def __init__(
        self,
        *,
        control_handlers: dict[str, Callable[[dict[str, Any]], Any]] | None = None,
        orchestration_enqueue: Callable[[dict[str, Any]], str | Awaitable[str]] | None = None,
        egress_publish: Callable[[dict[str, Any]], None] | None = None,
        seen_ttl_seconds: int | None = None,
        dedup_store: BusDedupPort | None = None,
        bus_guard: EngagementBusGuard | None = None,
        metrics: MetricsPort | None = None,
    ) -> None:
        self._control_handlers = control_handlers or {}
        self._orchestration_enqueue = orchestration_enqueue
        self._egress_publish = egress_publish
        self._seen: dict[str, float] = {}
        if seen_ttl_seconds is None:
            from bootstrap.settings import get_settings

            seen_ttl_seconds = get_settings().bus_seen_ttl_seconds
        self._seen_ttl = seen_ttl_seconds
        self._dedup_store = dedup_store
        self._bus_guard = bus_guard
        self._metrics = metrics

    def _engagement_id(self, envelope: dict[str, Any]) -> str:
        payload = envelope.get("payload", {})
        if not isinstance(payload, dict):
            payload = {}
        return extract_engagement_id(
            correlation_id=str(payload.get("correlation_id", "")),
            payload=payload,
        ) or ""

    def _is_duplicate(self, envelope: dict[str, Any]) -> bool:
        msg_id = str(envelope.get("message_id") or envelope.get("signature", ""))
        if not msg_id:
            return False
        now = time.time()
        expired = [k for k, ts in self._seen.items() if now - ts > self._seen_ttl]
        for k in expired:
            del self._seen[k]
        if msg_id in self._seen:
            return True
        self._seen[msg_id] = now
        return False

    def _is_content_duplicate(self, envelope: dict[str, Any]) -> bool:
        if self._dedup_store is None:
            return False
        fingerprint = envelope_fingerprint(envelope)
        duplicate = self._dedup_store.is_duplicate(fingerprint)
        if duplicate and self._bus_guard is not None:
            engagement_id = self._engagement_id(envelope)
            if engagement_id:
                self._bus_guard.record_dedup_hit(engagement_id, fingerprint)
        return duplicate

    async def route_envelope(self, envelope: dict[str, Any]) -> None:
        if self._is_duplicate(envelope):
            logger.info(
                "bus_dedup_dropped",
                reason="message_id",
                recipient=str(envelope.get("recipient", "")),
                engagement_id=self._engagement_id(envelope),
            )
            if self._metrics is not None:
                self._metrics.record_bus_dedup_dropped("message_id")
            return
        if self._is_content_duplicate(envelope):
            logger.info(
                "bus_dedup_dropped",
                reason="content_fingerprint",
                recipient=str(envelope.get("recipient", "")),
                engagement_id=self._engagement_id(envelope),
            )
            if self._metrics is not None:
                self._metrics.record_bus_dedup_dropped("content_fingerprint")
            return
        recipient = str(envelope.get("recipient", ""))
        msg_type = str(envelope.get("type", ""))

        if recipient == "egress" or msg_type == BusMessageType.CONTROL.value:
            if self._egress_publish is not None:
                self._egress_publish(envelope)
            return

        handler = self._control_handlers.get(recipient)
        if handler is not None:
            result = handler(envelope)
            if hasattr(result, "__await__"):
                await cast(Awaitable[Any], result)
            return

        if self._orchestration_enqueue is not None and recipient:
            result = self._orchestration_enqueue(envelope)
            if hasattr(result, "__await__"):
                await cast(Awaitable[Any], result)
