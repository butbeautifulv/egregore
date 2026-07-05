from __future__ import annotations

from typing import Any

from bootstrap.container import get_container
from cys_core.application.engagement_streaming import publish_assistant_snapshot
from cys_core.infrastructure.bus_transport import get_bus_transport
from interfaces.control_plane.control_message_handler import ControlMessageHandler
from interfaces.control_plane.narrator_factory import get_control_narrator
from interfaces.control_plane.status_store import get_status_store


class CoordinatorService(ControlMessageHandler):
    """Control tower — narrates worker activity for the user."""

    def __init__(self) -> None:
        self.store = get_status_store()
        self.transport = get_bus_transport()
        self._narrator = get_control_narrator()

    async def handle_message(self, envelope: dict[str, Any]) -> None:
        context = self.extract_context(envelope)
        summary = await self._narrator.narrate(context)
        self.store.record_narrative(
            {
                "investigation_id": context["investigation_id"],
                "tenant_id": context["tenant_id"],
                "summary": summary,
                "sender": context["sender"],
            }
        )
        investigation_id = context["investigation_id"]
        if investigation_id:
            container = get_container()
            egress = container.get_engagement_egress()
            egress.publish_event(
                investigation_id,
                "report",
                {
                    "summary": summary,
                    "persona": "coordinator",
                    "job_id": context["job_id"],
                    "tenant_id": context["tenant_id"],
                },
            )
            publish_assistant_snapshot(
                engagement_id=investigation_id,
                job_id=context["job_id"],
                persona="coordinator",
                tenant_id=context["tenant_id"],
                text=summary,
                egress=egress,
            )


_coordinator_service: CoordinatorService | None = None


def get_coordinator_service() -> CoordinatorService:
    global _coordinator_service
    if _coordinator_service is None:
        _coordinator_service = CoordinatorService()
    return _coordinator_service
