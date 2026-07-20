from __future__ import annotations

from typing import Any, Literal

from cys_core.domain.findings.operator_outcome import OperatorOutcome, OutcomeSection, ProvenanceRef


def _recommendations_from_finding(finding: dict[str, Any]) -> list[str]:
    for key in ("recommendations", "recommended_actions"):
        raw = finding.get(key)
        if isinstance(raw, list):
            return [str(item) for item in raw if str(item).strip()]
    return []


def _title_from_finding(finding: dict[str, Any], *, fallback: str) -> str:
    for key in ("title", "topic", "incident_id"):
        value = finding.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return fallback


def finding_to_operator_outcome(
    finding: dict[str, Any],
    *,
    kind: Literal["advisory", "investigation", "synthesis"] = "advisory",
    title: str = "",
    provenance: list[ProvenanceRef] | None = None,
) -> OperatorOutcome:
    summary = str(
        finding.get("summary") or finding.get("finding") or finding.get("topic") or ""
    ).strip()
    return OperatorOutcome(
        kind=kind,
        title=title or _title_from_finding(finding, fallback="Work order outcome"),
        summary=summary or "—",
        recommendations=_recommendations_from_finding(finding),
        provenance=provenance or [],
        confidence=float(finding.get("confidence", finding.get("trust_score", 0.5)) or 0.5),
        risk_level=str(finding.get("risk_level") or finding.get("priority") or "") or None,
        degraded=bool(finding.get("degraded")),
        references=[str(item) for item in (finding.get("references") or []) if str(item).strip()],
        sections=[
            OutcomeSection(title="Details", body=summary, items=_recommendations_from_finding(finding))
        ]
        if summary
        else [],
    )


def synthesis_outcome_from_context(
    finding: dict[str, Any],
    *,
    specialist_outcomes: list[dict[str, Any]] | None = None,
    degraded: bool = False,
) -> OperatorOutcome:
    provenance: list[ProvenanceRef] = []
    for item in specialist_outcomes or []:
        persona = str(item.get("persona", ""))
        if not persona:
            continue
        provenance.append(
            ProvenanceRef(
                persona=persona,
                job_id=str(item.get("job_id", "")),
                status=str(item.get("status", "completed")),
            )
        )
    outcome = finding_to_operator_outcome(
        finding,
        kind="synthesis",
        title=_title_from_finding(finding, fallback="Investigation outcome"),
        provenance=provenance,
    )
    outcome.degraded = degraded or bool(finding.get("degraded"))
    return outcome


def degraded_synthesis_outcome(
    *,
    reason: str,
    specialist_findings: list[dict[str, Any]],
) -> OperatorOutcome:
    provenance = [
        ProvenanceRef(
            persona=str(item.get("persona", "")),
            job_id=str(item.get("job_id", "")),
            status="failed" if item.get("status") == "failed" else "completed",
        )
        for item in specialist_findings
        if isinstance(item, dict) and item.get("persona")
    ]
    return OperatorOutcome(
        kind="synthesis",
        title="Degraded synthesis",
        summary=reason,
        degraded=True,
        provenance=provenance,
        recommendations=[],
        confidence=0.0,
    )
