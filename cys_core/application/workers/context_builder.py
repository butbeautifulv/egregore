from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from cys_core.application.ports.engagement_store import EngagementStateStore
from cys_core.domain.memory.services import MemoryReadService
from cys_core.domain.workers.models import WorkerJob


class WorkerContextBuilder:
    def __init__(
        self,
        *,
        engagement_store: EngagementStateStore | None = None,
        memory_reader: MemoryReadService | None = None,
        record_memory_read: Callable[[str, int], None] | None = None,
    ) -> None:
        self._engagement_store = engagement_store
        self._memory_reader = memory_reader
        self._record_memory_read = record_memory_read or (lambda _tenant, _count: None)

    def investigation_id(self, job: WorkerJob) -> str:
        parent_key = job.payload.get("parent_correlation_key")
        if parent_key:
            return str(parent_key)
        return job.correlation_id or job.event_id

    def build(self, job: WorkerJob) -> dict[str, Any]:
        investigation_id = self.investigation_id(job)
        context: dict[str, Any] = {"investigation_id": investigation_id, "tenant_id": job.tenant_id}
        if self._engagement_store is not None:
            engagement = self._engagement_store.get(job.tenant_id, investigation_id)
            if engagement is not None:
                context["state"] = engagement.model_dump(mode="json")
        if self._memory_reader is not None:
            entries = self._memory_reader.query_investigation(
                job.tenant_id,
                investigation_id,
                limit=10,
                requesting_tenant_id=job.tenant_id,
            )
            if entries:
                self._record_memory_read(job.tenant_id, len(entries))
                context["prior_findings"] = [
                    {
                        "agent": entry.source_agent,
                        "type": entry.memory_type,
                        "content": entry.content,
                        "job_id": entry.source_job_id,
                    }
                    for entry in entries
                ]
        return context

    def job_input(self, job: WorkerJob) -> str:
        if job.payload.get("phase") == "synthesis":
            evidence_manifests = job.payload.get("evidence_manifests") or {}
            if not evidence_manifests and self._engagement_store is not None:
                engagement = self._engagement_store.get(job.tenant_id, self.investigation_id(job))
                if engagement is not None:
                    evidence_manifests = engagement.evidence_manifests
            return json.dumps(
                {
                    "phase": "synthesis",
                    "original_goal": str(job.payload.get("goal", "")),
                    "specialist_findings": job.payload.get("findings_summary", []),
                    "specialist_outcomes": job.payload.get("specialist_outcomes", []),
                    "failed_personas": job.payload.get("failed_personas", []),
                    "planner_rationale": job.payload.get("planner_rationale", ""),
                    "evidence_manifests": evidence_manifests,
                    "instruction": (
                        "Собери единый ответ оператору: выводы, рекомендации, пробелы. "
                        "Пересказывай только утверждения, подтверждённые evidence[].obs_id "
                        "из specialist findings. При telemetry_level=sparse начни с неопределённости "
                        "и укажи data_gaps.remediation. Учти failed personas."
                    ),
                    "investigation_context": self.build(job),
                },
                ensure_ascii=False,
            )

        sub_goals = job.payload.get("sub_goals", {})
        if not isinstance(sub_goals, dict):
            sub_goals = {}
        engagement = (
            self._engagement_store.get(job.tenant_id, self.investigation_id(job))
            if self._engagement_store is not None
            else None
        )
        goal = str(job.payload.get("goal", job.payload.get("message", "")))
        if engagement is not None and engagement.goal:
            goal = engagement.goal
        if job.persona == "consultant":
            return json.dumps(
                {
                    "question": goal,
                    "sub_goal": str(sub_goals.get(job.persona, "")),
                    "planner_sub_goals": sub_goals,
                    "phase": job.payload.get("phase", "specialist"),
                    "investigation_context": self.build(job),
                },
                ensure_ascii=False,
            )
        return json.dumps(
            {
                "persona": job.persona,
                "goal": goal,
                "sub_goal": str(sub_goals.get(job.persona, "")),
                "planner_plan": job.payload.get("planner_plan", []),
                "phase": job.payload.get("phase", "specialist"),
                "event_id": job.event_id,
                "playbook_id": job.playbook_id,
                "payload": job.payload,
                "sandbox_id": job.sandbox_id,
                "feedback": job.feedback,
                "investigation_context": self.build(job),
            },
            ensure_ascii=False,
        )
