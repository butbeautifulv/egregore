from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from cys_core.application.bus_planner_gate import filter_bus_recipients_for_plan, filter_escalation_recipients
from cys_core.application.engagement_streaming import publish_assistant_snapshot
from cys_core.application.ports.bus import AgentTransportConnector
from cys_core.application.ports.engagement_egress import EngagementEgressPort
from cys_core.application.ports.engagement_store import EngagementStateStore
from cys_core.application.workers.noop_finding import is_noop_finding
from cys_core.application.workers.tool_execution_tracker import (
    get_merged_manifest,
    record_persona_manifest,
)
from cys_core.domain.memory.services import MemoryWriteService
from cys_core.domain.security.agent_bus import SecureAgentBus
from cys_core.domain.workers.models import WorkerJob

_CONTROL_BUS_PERSONAS = frozenset({"planner", "critic", "coordinator"})


def should_publish_finding_to_bus(*, persona: str, role: str | None = None) -> bool:
    """Control-plane personas plan/orchestrate; they do not emit worker findings on the bus."""
    if role == "control":
        return False
    return persona not in _CONTROL_BUS_PERSONAS


class WorkerFindingPublisher:
    def __init__(
        self,
        *,
        bus: SecureAgentBus,
        transport: AgentTransportConnector,
        memory_writer: MemoryWriteService | None = None,
        engagement_store: EngagementStateStore | None = None,
        engagement_egress: EngagementEgressPort | None = None,
        bus_guard: Any | None = None,
        record_memory_write: Callable[[str, str], None] | None = None,
    ) -> None:
        self._bus = bus
        self._transport = transport
        self._memory_writer = memory_writer
        self._engagement_store = engagement_store
        self._engagement_egress = engagement_egress
        self._bus_guard = bus_guard
        self._record_memory_write = record_memory_write or (lambda _tenant, _memory_type: None)

    def record_noop(self, *, job: WorkerJob, investigation_id: str) -> None:
        """Track noop churn for engagement guard without publishing to bus."""
        if self._bus_guard is None:
            return
        try:
            self._bus_guard.record_noop_publish(investigation_id, job.persona)
        except Exception:
            pass

    async def publish(
        self,
        *,
        job: WorkerJob,
        defn: Any,
        result: dict[str, Any],
        sandbox_id: str,
        investigation_id: str,
    ) -> None:
        if is_noop_finding(result):
            self.record_noop(job=job, investigation_id=investigation_id)
            return
        finding_payload = {
            "agent": job.persona,
            "event_id": job.event_id,
            "correlation_id": investigation_id,
            "tenant_id": job.tenant_id,
            "job_id": job.job_id,
            "data": result,
            "sandbox_id": sandbox_id,
        }
        role = getattr(defn, "role", None)
        if not should_publish_finding_to_bus(persona=job.persona, role=role):
            return
        recipients = list(dict.fromkeys([*(getattr(defn, "bus_recipients", None) or []), "critic"]))
        planner_plan: list[str] | None = None
        if self._engagement_store is not None:
            engagement = self._engagement_store.get(job.tenant_id, investigation_id)
            if engagement is not None and engagement.planner_plan:
                planner_plan = list(engagement.planner_plan)
        if planner_plan is None:
            planner_plan = list(job.payload.get("planner_plan") or [])
        recipients = filter_bus_recipients_for_plan(recipients, planner_plan)
        recipients = filter_escalation_recipients(job.persona, recipients, msg_type="finding")
        for recipient in recipients:
            envelope = self._bus.send_message(job.persona, recipient, "finding", finding_payload)
            self._bus.receive_message(recipient, envelope)
            envelope["message_id"] = envelope.get("signature", "")
            await self._transport.publish_delivery(envelope)

    def persist_memory(self, *, job: WorkerJob, result: dict[str, Any], investigation_id: str) -> None:
        if is_noop_finding(result):
            self.record_noop(job=job, investigation_id=investigation_id)
            return
        if self._memory_writer is None or not isinstance(result, dict):
            return
        entry = self._memory_writer.append_pending_finding(
            tenant_id=job.tenant_id,
            investigation_id=investigation_id,
            source_agent=job.persona,
            source_job_id=job.job_id,
            finding=result,
        )
        if entry is not None:
            self._record_memory_write(job.tenant_id, entry.memory_type)

    def append_engagement_finding(
        self,
        *,
        job: WorkerJob,
        result: dict[str, Any],
        investigation_id: str,
        is_final_report: bool = False,
    ) -> None:
        if is_noop_finding(result):
            self.record_noop(job=job, investigation_id=investigation_id)
            return
        if self._engagement_store is None or not isinstance(result, dict) or "error" in result:
            return
        finding_entry = {
            "persona": job.persona,
            "job_id": job.job_id,
            "finding": result,
        }
        manifest = get_merged_manifest(job.job_id)
        if manifest is not None:
            finding_entry["evidence_manifest"] = manifest.model_dump(mode="json")
            record_persona_manifest(investigation_id, job.persona, manifest)
            if self._engagement_store is not None:
                engagement = self._engagement_store.get(job.tenant_id, investigation_id)
                if engagement is not None:
                    engagement.evidence_manifests[job.persona] = manifest.model_dump(mode="json")
                    self._engagement_store.upsert(engagement)
        if is_final_report:
            finding_entry["is_final_report"] = True
        self._engagement_store.append_finding(
            job.tenant_id,
            investigation_id,
            finding_entry,
        )
        if self._engagement_egress is not None:
            publish_assistant_snapshot(
                egress=self._engagement_egress,
                engagement_id=investigation_id,
                job_id=job.job_id,
                persona=job.persona,
                tenant_id=job.tenant_id,
                text=json.dumps(result, indent=2, ensure_ascii=False),
            )

    def publish_final_report(
        self,
        *,
        job: WorkerJob,
        result: dict[str, Any],
        investigation_id: str,
    ) -> None:
        if self._engagement_store is None or not isinstance(result, dict):
            return
        self._engagement_store.set_final_report(job.tenant_id, investigation_id, result)
        if self._engagement_egress is None:
            return
        self._engagement_egress.publish_status(
            investigation_id,
            "final_report",
            {
                "tenant_id": job.tenant_id,
                "persona": job.persona,
                "job_id": job.job_id,
                "report": result,
            },
        )
        publish_assistant_snapshot(
            egress=self._engagement_egress,
            engagement_id=investigation_id,
            job_id=job.job_id,
            persona=job.persona,
            tenant_id=job.tenant_id,
            text=json.dumps(result, indent=2, ensure_ascii=False),
        )
