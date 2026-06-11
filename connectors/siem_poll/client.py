from __future__ import annotations

import asyncio
import signal
import uuid
from collections.abc import AsyncIterator
from typing import Any, Protocol

import httpx
import structlog

from connectors.siem_poll.models import RawSiemEvent, raw_to_security_event

logger = structlog.get_logger(__name__)


class SiemBackend(Protocol):
    """Protocol for SIEM data source backends."""

    async def fetch_events(self, since_id: str | None = None, limit: int = 100) -> list[RawSiemEvent]:
        """Fetch new events from the SIEM."""
        ...


class MockSiemBackend:
    """In-memory mock SIEM backend for development and testing."""

    def __init__(self) -> None:
        self._events: list[RawSiemEvent] = []
        self._next_id = 0

    def add_event(
        self,
        event_type: str = "alert",
        severity: str = "medium",
        host: str = "server-01",
        message: str = "Test event",
        **extra: Any,
    ) -> RawSiemEvent:
        """Add a mock event to the backend."""
        raw = RawSiemEvent(
            raw_id=f"mock-{self._next_id:06d}",
            event_type=event_type,
            severity=severity,
            source="mock-siem",
            host=host,
            message=message,
            extra=extra,
        )
        self._events.append(raw)
        self._next_id += 1
        return raw

    def seed_default_events(self) -> None:
        """Populate backend with a default set of test events."""
        self.add_event("alert", "high", "win-server-01", "PowerShell execution detected")
        self.add_event("edr.alert", "critical", "linux-host-02", "Privilege escalation attempt")
        self.add_event("iam.event", "medium", "ad-server", "Failed login", user="admin", ip="10.0.0.5")
        self.add_event("netflow", "high", "fw-01", "Outbound beacon detected", dst="198.51.100.1")
        self.add_event("dns", "low", "dns-01", "Suspicious DNS lookup", query="evil.example.com")

    async def fetch_events(self, since_id: str | None = None, limit: int = 100) -> list[RawSiemEvent]:
        if since_id is None:
            return self._events[:limit]
        try:
            idx = next(i for i, e in enumerate(self._events) if e.raw_id == since_id)
            return self._events[idx + 1 : idx + 1 + limit]
        except StopIteration:
            return self._events[:limit]


class SiemPollClient:
    """Polls a SIEM backend and POSTs normalized events to the Ingress API."""

    def __init__(
        self,
        *,
        backend: SiemBackend | None = None,
        ingress_url: str = "http://localhost:8080",
        poll_interval: float = 5.0,
        batch_size: int = 50,
        max_events: int = 0,
    ) -> None:
        self.backend = backend or MockSiemBackend()
        self.ingress_url = ingress_url.rstrip("/")
        self.poll_interval = poll_interval
        self.batch_size = batch_size
        self.max_events = max_events
        self._stop_event = asyncio.Event()
        self._last_id: str | None = None
        self._events_sent = 0

    def _setup_signals(self) -> None:
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._stop_event.set)

    async def _post_event(self, client: httpx.AsyncClient, raw: RawSiemEvent) -> bool:
        """Normalize and POST one event to Ingress API. Returns True on success."""
        try:
            event = raw_to_security_event(raw)
            payload = {
                "event_type": event.type,
                "payload": event.payload,
                "severity": event.severity,
                "source": event.source,
                "correlation_id": event.correlation_id,
            }
            response = await client.post(f"{self.ingress_url}/events", json=payload, timeout=10.0)
            response.raise_for_status()
            self._last_id = raw.raw_id
            self._events_sent += 1
            logger.info(
                "siem_poll.event_sent",
                raw_id=raw.raw_id,
                event_type=event.type,
                severity=event.severity,
            )
            return True
        except Exception as exc:
            logger.warning("siem_poll.send_failed", raw_id=raw.raw_id, error=str(exc))
            return False

    async def poll_once(self, client: httpx.AsyncClient) -> int:
        """Fetch one batch and POST each event. Returns count of events sent."""
        raw_events = await self.backend.fetch_events(since_id=self._last_id, limit=self.batch_size)
        sent = 0
        for raw in raw_events:
            if self._stop_event.is_set():
                break
            if await self._post_event(client, raw):
                sent += 1
            if self.max_events > 0 and self._events_sent >= self.max_events:
                self._stop_event.set()
                break
        return sent

    async def run(self) -> int:
        """Run poll loop until stopped. Returns total events sent."""
        self._setup_signals()
        logger.info(
            "siem_poll.started",
            ingress_url=self.ingress_url,
            poll_interval=self.poll_interval,
            batch_size=self.batch_size,
        )

        async with httpx.AsyncClient() as client:
            while not self._stop_event.is_set():
                await self.poll_once(client)
                if not self._stop_event.is_set():
                    try:
                        await asyncio.wait_for(
                            asyncio.shield(self._stop_event.wait()),
                            timeout=self.poll_interval,
                        )
                    except asyncio.TimeoutError:
                        pass

        logger.info("siem_poll.stopped", events_sent=self._events_sent)
        return self._events_sent
