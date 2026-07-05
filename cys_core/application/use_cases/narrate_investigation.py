from __future__ import annotations

import json
from typing import Any, Protocol

from cys_core.application.ports.engagement_store import EngagementStateStore
from cys_core.application.ports.tracing_ports import ApplicationTracingPort, NOOP_APPLICATION_TRACING
from cys_core.domain.memory.services import MemoryReadService


class NarratorRuntime(Protocol):
    async def arun(
        self,
        name: str,
        user_input: str,
        *,
        session_id: str | None = None,
        tenant_id: str | None = None,
        investigation_id: str | None = None,
    ) -> dict[str, Any]: ...


class NarrateInvestigationProgress:
    """Generate coordinator narrative from investigation state and episodic memory."""

    def __init__(
        self,
        *,
        runtime: NarratorRuntime | None = None,
        engagement_store: EngagementStateStore,
        memory_reader: MemoryReadService,
        coordinator_persona: str = "coordinator",
        application_tracing: ApplicationTracingPort | None = None,
    ) -> None:
        self.runtime = runtime
        self.engagement_store = engagement_store
        self.memory_reader = memory_reader
        self.coordinator_persona = coordinator_persona
        self._tracing = application_tracing or NOOP_APPLICATION_TRACING

    def _fallback_narrative(
        self,
        sender: str,
        event_id: str,
        state_summary: dict[str, Any],
        *,
        finding: dict[str, Any] | None = None,
    ) -> str:
        completed = ", ".join(state_summary.get("completed_personas", [])) or "нет"
        findings_count = len(state_summary.get("findings_summary", []))
        finding_summary = ""
        if isinstance(finding, dict):
            finding_summary = str(
                finding.get("summary") or finding.get("finding") or finding.get("topic") or ""
            ).strip()
        base = (
            f"Агент {sender} завершил обработку события {event_id}. "
            f"Расследование: завершённые роли [{completed}], findings={findings_count}."
        )
        if finding_summary:
            return f"{base} Краткий итог: {finding_summary[:500]}"
        return base

    async def execute(
        self,
        *,
        sender: str,
        event_id: str,
        tenant_id: str,
        investigation_id: str,
        finding: dict[str, Any] | None = None,
    ) -> str:
        with self._tracing.span(
            "control.coordinator.narrate",
            engagement_id=investigation_id,
            tenant_id=tenant_id,
            persona=self.coordinator_persona,
        ):
            return await self._execute_narrate(
                sender=sender,
                event_id=event_id,
                tenant_id=tenant_id,
                investigation_id=investigation_id,
                finding=finding,
            )

    async def _execute_narrate(
        self,
        *,
        sender: str,
        event_id: str,
        tenant_id: str,
        investigation_id: str,
        finding: dict[str, Any] | None = None,
    ) -> str:
        state = self.engagement_store.get(tenant_id, investigation_id)
        state_summary = state.model_dump(mode="json") if state else {}
        entries = self.memory_reader.query_investigation(tenant_id, investigation_id, limit=5)
        memory_lines = self.memory_reader.format_for_prompt(entries, max_chars=2000)

        if self.runtime is None:
            return self._fallback_narrative(sender, event_id, state_summary, finding=finding)

        prompt = json.dumps(
            {
                "sender": sender,
                "event_id": event_id,
                "investigation_state": state_summary,
                "recent_memory": memory_lines,
                "incoming_finding": finding or {},
                "instructions": "Write a short Russian status narrative for the security operator.",
            },
            ensure_ascii=False,
        )
        try:
            result = await self.runtime.arun(
                self.coordinator_persona,
                prompt,
                session_id=f"coordinator:{investigation_id}",
                tenant_id=tenant_id,
                investigation_id=investigation_id,
            )
            text = result.get("raw_response") or result.get("response") or result.get("narrative")
            if isinstance(text, str) and text.strip():
                return text.strip()
        except Exception:
            pass
        return self._fallback_narrative(sender, event_id, state_summary, finding=finding)
