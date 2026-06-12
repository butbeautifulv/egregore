from __future__ import annotations

from typing import Any

from cys_core.infrastructure.bus_transport import get_bus_transport
from interfaces.control_plane.status_store import get_status_store


class CoordinatorService:
    """Control tower — narrates worker activity for the user."""

    def __init__(self) -> None:
        self.store = get_status_store()
        self.transport = get_bus_transport()

    async def handle_message(self, envelope: dict[str, Any]) -> None:
        sender = envelope.get("sender", "unknown")
        payload = envelope.get("payload", {})
        event_id = payload.get("event_id", "n/a")
        narrative = f"Агент {sender} завершил обработку события {event_id}."
        self.store.record_narrative(narrative)

    def register(self) -> None:
        self.transport.subscribe("coordinator", self.handle_message)


_coordinator_service: CoordinatorService | None = None


def get_coordinator_service() -> CoordinatorService:
    global _coordinator_service
    if _coordinator_service is None:
        _coordinator_service = CoordinatorService()
        _coordinator_service.register()
    return _coordinator_service
