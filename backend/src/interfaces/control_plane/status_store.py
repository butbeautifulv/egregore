from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from bootstrap.settings import settings

StatusCallback = Callable[[str, dict[str, Any]], None]


@dataclass
class MemoryStatusStore:
    """In-memory user-facing status feed."""

    events: list[dict[str, Any]] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)
    critic_feedback: list[dict[str, Any]] = field(default_factory=list)
    coordinator_narratives: list[str] = field(default_factory=list)
    awaiting_approval: list[dict[str, Any]] = field(default_factory=list)
    escalations: list[dict[str, Any]] = field(default_factory=list)
    _subscribers: list[StatusCallback] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def subscribe(self, callback: StatusCallback) -> Callable[[], None]:
        with self._lock:
            self._subscribers.append(callback)

        def unsubscribe() -> None:
            with self._lock:
                if callback in self._subscribers:
                    self._subscribers.remove(callback)

        return unsubscribe

    def _notify(self, kind: str, payload: dict[str, Any]) -> None:
        with self._lock:
            subscribers = list(self._subscribers)
        event = {"kind": kind, "payload": payload, "ts": datetime.now(UTC).isoformat()}
        for callback in subscribers:
            callback(kind, event)

    def record_event(self, event: dict[str, Any]) -> None:
        self.events.append(event)
        self._notify("event", event)

    def record_finding(self, envelope: dict[str, Any]) -> None:
        self.findings.append(envelope)
        self._notify("finding", envelope)

    def record_critic(self, feedback: dict[str, Any]) -> None:
        self.critic_feedback.append(feedback)
        self._notify("critic", feedback)

    def record_narrative(self, text: str) -> None:
        self.coordinator_narratives.append(text)
        self._notify("narrative", {"text": text})

    def record_awaiting_approval(self, record: dict[str, Any]) -> None:
        self.awaiting_approval.append(record)
        self._notify("awaiting_approval", record)

    def record_escalation(self, record: dict[str, Any]) -> None:
        self.escalations.append(record)
        self._notify("escalation", record)

    def record_investigation_update(self, payload: dict[str, Any]) -> None:
        self._notify("investigation", payload)

    def snapshot(self) -> dict[str, Any]:
        return {
            "events_count": len(self.events),
            "findings_count": len(self.findings),
            "latest_narrative": self.coordinator_narratives[-1] if self.coordinator_narratives else "",
            "events": self.events[-20:],
            "findings": self.findings[-20:],
            "critic_feedback": self.critic_feedback[-20:],
            "narratives": self.coordinator_narratives[-10:],
            "awaiting_approval": self.awaiting_approval[-20:],
            "escalations": self.escalations[-20:],
        }


_status_store: MemoryStatusStore | Any | None = None


def _create_status_store():
    connector = settings.status_store_connector.lower()
    if connector == "memory" or settings.use_memory_fallback:
        return MemoryStatusStore()
    if connector in ("postgres", "auto"):
        try:
            from interfaces.control_plane.postgres_status_store import PostgresStatusStore

            return PostgresStatusStore(settings.postgres_url)
        except Exception:
            if connector == "postgres":
                raise
    return MemoryStatusStore()


def get_status_store():
    global _status_store
    if _status_store is None:
        _status_store = _create_status_store()
    return _status_store


def reset_status_store() -> None:
    global _status_store
    _status_store = None
