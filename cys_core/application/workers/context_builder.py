from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from cys_core.application.bus_engagement import normalize_correlation_id
from cys_core.application.ports.engagement_store import EngagementStateStore
from cys_core.domain.follow_up.models import is_follow_up_payload, work_kind_from_payload
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
            return normalize_correlation_id(str(parent_key), job.payload)
        raw = job.correlation_id or job.event_id
        return normalize_correlation_id(str(raw), job.payload)

    def build(self, job: WorkerJob) -> dict[str, Any]:
        investigation_id = self.investigation_id(job)
        context: dict[str, Any] = {"investigation_id": investigation_id, "tenant_id": job.tenant_id}
        if self._engagement_store is not None:
            engagement = self._engagement_store.get(job.tenant_id, investigation_id)
            if engagement is not None:
                context["state"] = engagement.model_dump(mode="json")
                workspace_id = (getattr(engagement, "workspace_id", "") or "").strip()
                if workspace_id:
                    context["workspace_id"] = workspace_id
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
                    if entry.memory_type != "conversation"
                ]
        return context

    def _operator_context(self, job: WorkerJob, engagement) -> dict[str, Any]:
        investigation_id = self.investigation_id(job)
        work_kind = work_kind_from_payload(job.payload)
        prior_turns: list[dict[str, Any]] = []
        if self._memory_reader is not None:
            for entry in self._memory_reader.query_conversation_turns(
                job.tenant_id,
                investigation_id,
                limit=50,
            ):
                try:
                    prior_turns.append(json.loads(entry.content))
                except json.JSONDecodeError:
                    continue
        findings_summary = engagement.findings_summary if engagement else []
        if work_kind == "initial_qa":
            findings_summary = []
        return {
            "current_message": str(job.payload.get("operator_message", "")),
            "prior_turns": prior_turns,
            "context_summary": getattr(engagement, "context_summary", "") if engagement else "",
            "final_report": engagement.final_report if engagement else None,
            "findings_summary": findings_summary,
            "evidence_manifests": engagement.evidence_manifests if engagement else {},
        }

    def _follow_up_instruction(self, work_kind: str) -> str:
        if work_kind == "initial_qa":
            return (
                "Initial operator Q&A (no investigation yet): provide read-only advisory guidance "
                "based on the operator message, goal, and intake context only. Do not call SIEM/Veil tools."
            )
        if work_kind == "follow_up_orchestrate":
            return (
                "Operator follow-up: answer from structured evidence or spawn_worker for reinvestigation. "
                "Do not call SIEM/Veil directly. Cite evidence_manifest obs_id refs."
            )
        return (
            "Operator follow-up Q&A: answer using final_report, findings_summary, and evidence_manifests only. "
            "Do not call SIEM/Veil tools."
        )

    def _skill_hints(self, message: str) -> list[str]:
        hints: list[str] = []
        lower = message.lower()
        mapping = {
            "siem": "threat-intel-osint",
            "ioc": "threat-intel-osint",
            "network": "network-beaconing",
            "forensic": "digital-forensics",
            "cloud": "cloud-threat-detection",
        }
        for keyword, skill_id in mapping.items():
            if keyword in lower and skill_id not in hints:
                hints.append(skill_id)
        if not hints:
            return []
        try:
            from cys_core.registry.skill_registry import SkillRegistry

            reg = SkillRegistry.load()
            return [name for name in reg.names() if name in hints]
        except Exception:
            return hints

    def job_input(self, job: WorkerJob) -> str:
        work_kind = work_kind_from_payload(job.payload)
        if is_follow_up_payload(job.payload):
            engagement = (
                self._engagement_store.get(job.tenant_id, self.investigation_id(job))
                if self._engagement_store is not None
                else None
            )
            operator_message = str(job.payload.get("operator_message", ""))
            skill_names = self._skill_hints(operator_message) if work_kind == "follow_up_orchestrate" else []
            skill_block = ""
            if skill_names:
                try:
                    from cys_core.registry.skill_registry import SkillRegistry

                    skill_block = SkillRegistry.load().metadata_block(skill_names)
                except Exception:
                    skill_block = ""
            return json.dumps(
                {
                    "persona": job.persona,
                    "phase": job.payload.get("phase", "follow_up"),
                    "work_kind": work_kind,
                    "operator_context": self._operator_context(job, engagement),
                    "follow_up_instruction": self._follow_up_instruction(work_kind),
                    "skill_hints": skill_names,
                    "available_skills": skill_block,
                    "investigation_context": self.build(job),
                },
                ensure_ascii=False,
            )
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
        evidence_manifest = None
        if engagement is not None:
            evidence_manifest = engagement.evidence_manifests.get(job.persona)
        revision_instruction = ""
        if job.feedback:
            revision_instruction = (
                "Critic revision: address feedback without re-running investigate_incident. "
                "Cite evidence_manifest observations via evidence[].obs_id refs."
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
                "evidence_manifest": evidence_manifest,
                "revision_instruction": revision_instruction,
                "investigation_context": self.build(job),
                "tool_hints": self._tool_hints(job.persona),
            },
            ensure_ascii=False,
        )

    @staticmethod
    def _tool_hints(persona: str) -> dict[str, str]:
        if persona != "intel":
            return {}
        return {
            "ti_search_in_category": "Required args: category (ti|vuln|mitre|playbook), query (non-empty string)",
            "playbook_for_technique": "Required args: technique_id (e.g. T1059)",
            "enrich_ioc": "Required args: query, category (alias: ti for IOC)",
        }
