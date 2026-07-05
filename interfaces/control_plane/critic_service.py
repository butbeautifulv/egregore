from __future__ import annotations

import json
from typing import Any

from bootstrap.container import get_container
from cys_core.application.engagement_streaming import publish_assistant_snapshot
from cys_core.application.workers.noop_finding import is_noop_finding
from cys_core.domain.security.bus_messages import BusMessageType
from cys_core.infrastructure.bus_transport import get_bus_transport
from interfaces.control_plane.control_message_handler import ControlMessageHandler
from interfaces.worker.orchestrator import build_agent_bus


class CriticService(ControlMessageHandler):
    """Async bus subscriber — validates findings and routes revisions via bus."""

    def __init__(self) -> None:
        self.transport = get_bus_transport()
        from cys_core.application.use_cases.process_finding_critic import ProcessFindingCritic

        settings = get_container().settings
        container = get_container()
        self._critic = ProcessFindingCritic(
            policy_port=container.get_profile_policy_port(),
            application_tracing=container.get_application_tracing_port(),
            runtime=container.get_agent_runtime() if settings.critic_use_llm_judge else None,
            use_llm_judge=settings.critic_use_llm_judge,
            schema_registry=container.get_schema_registry_port(),
        )

    async def _enqueue_revision(self, envelope: dict[str, Any], feedback: str) -> None:
        payload = dict(envelope.get("payload", {}))
        persona = str(envelope.get("sender", payload.get("agent", "soc")))

        bus = build_agent_bus()
        revision_payload = {**payload, "feedback": feedback}
        revision_envelope = bus.send_message("critic", persona, BusMessageType.REVISION.value, revision_payload)
        revision_envelope["message_id"] = revision_envelope.get("signature", "")
        await self.transport.publish_delivery(revision_envelope)

    async def handle_message(self, envelope: dict[str, Any]) -> dict[str, Any]:
        context = self.extract_context(envelope)
        payload = context["payload"]
        finding = context["finding"]
        persona = context["sender"]
        tenant_id = context["tenant_id"]
        engagement_id = context["investigation_id"]
        job_id = context["job_id"]

        result = await self._critic.execute_async(
            persona=persona,
            finding=finding if isinstance(finding, dict) else {},
            investigation_id=engagement_id,
            tenant_id=tenant_id,
        )
        if not result.get("passed", True) and not is_noop_finding(finding if isinstance(finding, dict) else {}):
            await self._enqueue_revision(envelope, feedback="critic_revision_requested")

        if engagement_id:
            container = get_container()
            egress = container.get_engagement_egress()
            egress.publish_event(
                engagement_id,
                "control",
                {
                    "verdict": result,
                    "persona": "critic",
                    "job_id": job_id,
                    "source_persona": persona,
                    "tenant_id": tenant_id,
                },
            )
            publish_assistant_snapshot(
                engagement_id=engagement_id,
                job_id=job_id,
                persona="critic",
                tenant_id=tenant_id,
                text=json.dumps(result, indent=2, ensure_ascii=False),
                egress=egress,
            )
        return result


_critic_service: CriticService | None = None


def get_critic_service() -> CriticService:
    global _critic_service
    if _critic_service is None:
        _critic_service = CriticService()
    return _critic_service
