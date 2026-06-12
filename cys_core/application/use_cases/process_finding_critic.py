from __future__ import annotations

from typing import Any, Awaitable, Callable, Protocol

from cys_core.domain.security.guardrails import OutputGuardrails


class CriticStatusStore(Protocol):
    def record_finding(self, envelope: dict[str, Any]) -> None: ...
    def record_critic(self, feedback: dict[str, Any]) -> None: ...
    def record_awaiting_approval(self, record: dict[str, Any]) -> None: ...
    def record_escalation(self, record: dict[str, Any]) -> None: ...


class ProcessFindingCritic:
    """Validate finding envelope, optional L2 HITL, and escalation."""

    def __init__(
        self,
        *,
        guardrails: OutputGuardrails,
        store: CriticStatusStore,
        trust_score_threshold: float,
        publish_awaiting_approval: Callable[[dict[str, Any]], Awaitable[None]],
        publish_escalation_event: Callable[..., Awaitable[bool]],
    ) -> None:
        self.guardrails = guardrails
        self.store = store
        self.trust_score_threshold = trust_score_threshold
        self.publish_awaiting_approval = publish_awaiting_approval
        self.publish_escalation_event = publish_escalation_event

    def _trust_score(self, payload: dict[str, Any]) -> float:
        data = payload.get("data", payload)
        if isinstance(data, dict):
            conf = data.get("confidence")
            if conf is not None:
                return float(conf)
            priority = str(data.get("priority", data.get("severity", ""))).lower()
            if priority in ("critical", "high"):
                return 0.4
            if priority in ("medium",):
                return 0.7
        return 0.85

    def _finding_severity(self, payload: dict[str, Any]) -> str:
        data = payload.get("data", payload)
        if isinstance(data, dict):
            return str(data.get("severity", data.get("priority", "medium"))).lower()
        return "medium"

    def _should_escalate(self, payload: dict[str, Any]) -> bool:
        return self._finding_severity(payload) in ("critical", "high")

    async def execute(self, envelope: dict[str, Any]) -> dict[str, Any]:
        payload = envelope.get("payload", {})
        trust_score = self._trust_score(payload)
        issues: list[str] = []
        if trust_score < self.trust_score_threshold:
            issues.append("low_trust_score")
        data = payload.get("data", {})
        feedback = {
            "sender": envelope.get("sender"),
            "event_id": payload.get("event_id"),
            "trust_score": trust_score,
            "issues_detected": issues,
            "approved": not issues,
        }
        self.store.record_finding(envelope)
        self.store.record_critic(feedback)

        findings = [{"data": data if isinstance(data, dict) else payload}]
        needs_hitl = self.guardrails.requires_hitl(
            findings,
            trust_score,
            self.trust_score_threshold,
        )
        if needs_hitl:
            approval_record = {
                "event_id": payload.get("event_id"),
                "sender": envelope.get("sender"),
                "trust_score": trust_score,
                "issues_detected": issues,
                "envelope": envelope,
            }
            self.store.record_awaiting_approval(approval_record)
            await self.publish_awaiting_approval(approval_record)
            feedback["requires_hitl"] = True
        elif not needs_hitl and self._should_escalate(payload):
            severity = self._finding_severity(payload)
            escalated = await self.publish_escalation_event(
                event_id=f"esc-{payload.get('event_id', 'unknown')}",
                source_persona=str(envelope.get("sender", "unknown")),
                payload={
                    "finding": data if isinstance(data, dict) else payload,
                    "event_id": payload.get("event_id"),
                    "original_sender": envelope.get("sender"),
                },
                severity="critical" if severity == "critical" else "high",
                correlation_id=str(payload.get("correlation_id", payload.get("event_id", ""))),
            )
            feedback["escalated"] = escalated
            if escalated:
                self.store.record_escalation(
                    {
                        "event_id": payload.get("event_id"),
                        "source_persona": envelope.get("sender"),
                        "severity": severity,
                    }
                )

        return feedback

    async def escalate_after_l2_approval(self, approval_record: dict[str, Any]) -> bool:
        envelope = approval_record.get("envelope", {})
        payload = envelope.get("payload", {})
        severity = self._finding_severity(payload)
        escalated = await self.publish_escalation_event(
            event_id=f"esc-{payload.get('event_id', 'unknown')}",
            source_persona=str(envelope.get("sender", approval_record.get("sender", "unknown"))),
            payload={
                "finding": payload.get("data", payload),
                "event_id": payload.get("event_id"),
                "l2_approved": True,
            },
            severity="critical" if severity == "critical" else "high",
            correlation_id=str(payload.get("correlation_id", payload.get("event_id", ""))),
        )
        if escalated:
            self.store.record_escalation(
                {
                    "event_id": payload.get("event_id"),
                    "source_persona": envelope.get("sender"),
                    "severity": severity,
                    "l2_approved": True,
                }
            )
        return escalated
