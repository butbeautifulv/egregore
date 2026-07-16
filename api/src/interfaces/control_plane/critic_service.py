from __future__ import annotations

from typing import Any

from bootstrap.container import get_container
from cys_core.application.bus_engagement import extract_engagement_id, normalize_correlation_id
from cys_core.application.control_plane.critic_display import (
    critic_verdict_visible_to_operator,
    format_critic_operator_message,
    format_soc_revision_manifest_hint,
)
from cys_core.application.engagement_bus_guard import get_engagement_bus_guard
from cys_core.application.engagement_streaming import publish_assistant_snapshot
from cys_core.application.workers.noop_finding import is_noop_finding
from cys_core.application.workers.tool_execution_tracker import resolve_persona_manifest
from cys_core.domain.security.bus_messages import BusMessageType
from cys_core.infrastructure.bus_transport import get_bus_transport
from interfaces.control_plane.control_message_handler import ControlMessageHandler
from interfaces.worker.orchestrator import build_agent_bus


class CriticService(ControlMessageHandler):
    """Async bus subscriber — validates findings and routes revisions via bus."""

    def __init__(self) -> None:
        self.transport = get_bus_transport()
        from cys_core.application.use_cases.process_finding_critic import ProcessFindingCritic

        container = get_container()
        self._critic = ProcessFindingCritic(
            policy_port=container.get_profile_policy_port(),
            application_tracing=container.get_application_tracing_port(),
            schema_registry=container.get_schema_registry_port(),
            engagement_store=container.get_engagement_state_store(),
        )

    async def _enqueue_revision(self, envelope: dict[str, Any], feedback: str) -> bool:
        payload = dict(envelope.get("payload", {}))
        persona = str(envelope.get("sender", payload.get("agent", "soc")))
        correlation_id = normalize_correlation_id(
            str(payload.get("correlation_id", "")),
            payload,
        )
        engagement_id = extract_engagement_id(correlation_id=correlation_id, payload=payload)
        if persona == "soc" and engagement_id:
            # NOTE(evidence-grounding-consolidation, 2026-07-14, fixed by 5-whys root cause #1):
            # now reads through the durable EngagementStateStore first (worker and this
            # CriticService instance run in separate processes/containers in every real
            # deployment topology here) — see resolve_persona_manifest() and the note above
            # record_evidence_manifest in cys_core/application/workers/tool_execution_tracker.py.
            tenant_id = str(payload.get("tenant_id", "default"))
            manifest = resolve_persona_manifest(
                get_container().get_engagement_state_store(),
                tenant_id=tenant_id,
                investigation_id=engagement_id,
                persona="soc",
            )
            if manifest is not None:
                feedback = f"{feedback}{format_soc_revision_manifest_hint(manifest)}"
        settings = get_container().settings
        guard = get_engagement_bus_guard()
        if engagement_id and guard.revision_cap_exceeded(
            engagement_id,
            persona,
            max_revisions=settings.bus_max_revisions_per_persona,
        ):
            return False

        bus = build_agent_bus()
        revision_payload = {**payload, "feedback": feedback}
        revision_envelope = bus.send_message("critic", persona, BusMessageType.REVISION.value, revision_payload)
        revision_envelope["message_id"] = revision_envelope.get("signature", "")
        await self.transport.publish_delivery(revision_envelope)
        return True

    async def handle_message(self, envelope: dict[str, Any]) -> dict[str, Any]:
        context = self.extract_context(envelope)
        context["payload"]
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
            settings = get_container().settings
            guard = get_engagement_bus_guard()
            cap_exceeded = bool(
                engagement_id
                and guard.revision_cap_exceeded(
                    engagement_id,
                    persona,
                    max_revisions=settings.bus_max_revisions_per_persona,
                )
            )
            if cap_exceeded:
                result = {
                    **result,
                    "passed": True,
                    "auto_accepted_after_revision_cap": True,
                }
            else:
                feedback = format_critic_operator_message(result, source_persona=persona)
                if await self._enqueue_revision(envelope, feedback=feedback):
                    result = {**result, "revision_enqueued": True}
                else:
                    result = {
                        **result,
                        "passed": True,
                        "auto_accepted_after_revision_cap": True,
                    }

        if engagement_id and critic_verdict_visible_to_operator(result):
            container = get_container()
            egress = container.get_engagement_egress()
            operator_text = format_critic_operator_message(result, source_persona=persona)
            egress.publish_event(
                engagement_id,
                "control",
                {
                    "verdict": result,
                    "persona": "critic",
                    "job_id": job_id,
                    "source_persona": persona,
                    "tenant_id": tenant_id,
                    "operator_message": operator_text,
                },
            )
            publish_assistant_snapshot(
                engagement_id=engagement_id,
                job_id=job_id,
                persona="critic",
                tenant_id=tenant_id,
                text=operator_text,
                egress=egress,
            )
        return result


_critic_service: CriticService | None = None


def get_critic_service() -> CriticService:
    global _critic_service
    if _critic_service is None:
        _critic_service = CriticService()
    return _critic_service
