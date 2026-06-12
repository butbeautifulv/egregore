from __future__ import annotations

from typing import Any

from bootstrap.settings import settings
from cys_core.application.use_cases.process_finding_critic import ProcessFindingCritic
from cys_core.domain.security.guardrails import OutputGuardrails
from cys_core.infrastructure.bus_transport import get_bus_transport
from cys_core.infrastructure.kafka_control_events import (
    publish_awaiting_approval,
    publish_escalation_event,
)
from interfaces.control_plane.status_store import get_status_store


class CriticService:
    """Async bus subscriber — validates findings, L2 HITL, and escalation."""

    def __init__(self, guardrails: OutputGuardrails | None = None) -> None:
        self.guardrails = guardrails or OutputGuardrails()
        self.store = get_status_store()
        self.transport = get_bus_transport()

    def _processor(self) -> ProcessFindingCritic:
        return ProcessFindingCritic(
            guardrails=self.guardrails,
            store=self.store,
            trust_score_threshold=settings.trust_score_threshold,
            publish_awaiting_approval=publish_awaiting_approval,
            publish_escalation_event=publish_escalation_event,
        )

    async def handle_message(self, envelope: dict[str, Any]) -> dict[str, Any]:
        return await self._processor().execute(envelope)

    async def escalate_after_l2_approval(self, approval_record: dict[str, Any]) -> bool:
        return await self._processor().escalate_after_l2_approval(approval_record)

    def register(self) -> None:
        self.transport.subscribe("critic", self.handle_message)


_critic_service: CriticService | None = None


def get_critic_service() -> CriticService:
    global _critic_service
    if _critic_service is None:
        _critic_service = CriticService()
        _critic_service.register()
    return _critic_service
