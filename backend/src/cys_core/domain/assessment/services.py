from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cys_core.domain.assessment.models import AssessmentReport, PendingApproval
from cys_core.domain.security.guardrails import OutputGuardrails
from cys_core.domain.security.risk import parse_threshold


@dataclass(frozen=True)
class HitlDecision:
    approved: bool
    pending_approval: dict[str, Any] | None
    interrupt_preview: dict[str, Any] | None = None


class HitlPolicy:
    """Domain policy for assessment approval requirements."""

    def __init__(self, guardrails: OutputGuardrails | None = None) -> None:
        self.guardrails = guardrails or OutputGuardrails()

    def preview(self, trust_score: float, findings: list[dict[str, Any]]) -> dict[str, Any]:
        pending = PendingApproval(
            trust_score=trust_score,
            findings_count=len(findings),
            high_severity=[
                f for f in findings if str(f.get("data", {}).get("severity", "")).lower() in ("high", "critical")
            ],
            message="Human approval required before publishing assessment report.",
        )
        return pending.model_dump()

    def decide(
        self,
        *,
        critic_result: dict[str, Any],
        findings: list[dict[str, Any]],
        trust_score_threshold: float,
        stage: str,
        auto_approve_threshold: str,
        manual_decision: bool | dict[str, Any] | None = None,
    ) -> HitlDecision:
        trust_score = float(critic_result.get("trust_score", 0.0))
        needs_approval = self.guardrails.requires_hitl(
            findings,
            trust_score,
            trust_score_threshold,
        )
        if not needs_approval:
            return HitlDecision(approved=True, pending_approval=None)

        if stage == "dev" and parse_threshold(auto_approve_threshold) >= parse_threshold("medium"):
            return HitlDecision(
                approved=True,
                pending_approval={"auto_approved": True, "reason": "dev stage"},
            )

        preview = self.preview(trust_score, findings)
        if manual_decision is None:
            return HitlDecision(approved=False, pending_approval=preview, interrupt_preview=preview)
        if isinstance(manual_decision, bool):
            approved = bool(manual_decision)
        else:
            approved = manual_decision.get("approved", False)
        return HitlDecision(approved=approved, pending_approval=preview)


class AssessmentReportBuilder:
    """Build assessment reports from domain state."""

    def build(self, state: dict[str, Any]) -> dict[str, Any]:
        if not state.get("approved"):
            return {
                "status": "rejected",
                "reason": "Assessment not approved",
                "pending_approval": state.get("pending_approval"),
            }

        return AssessmentReport(
            status="published",
            session_id=state.get("session_id"),
            findings=state.get("findings", []),
            critic_result=state.get("critic_result"),
            errors=state.get("errors", []),
        ).model_dump(exclude_none=True)
