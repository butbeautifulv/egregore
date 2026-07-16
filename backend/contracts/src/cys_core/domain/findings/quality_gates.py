from __future__ import annotations

from typing import Any

from cys_core.domain.evidence.gaps import consultant_synthesis_gaps, soc_evidence_gaps
from cys_core.domain.evidence.models import EvidenceManifest
from cys_core.domain.findings.normalize import normalize_finding_payload, normalize_list_field, structured_has_content


def normalize_consultant_lists(result: dict[str, Any]) -> None:
    if not result.get("recommendations") and result.get("recommended_actions"):
        result["recommendations"] = result["recommended_actions"]
    normalize_list_field(result, "recommendations")
    normalize_list_field(result, "references")


def _consultant_recommendations(result: dict[str, Any]) -> list[str]:
    recs = result.get("recommendations")
    if isinstance(recs, list):
        return [str(item).strip() for item in recs if str(item).strip()]
    return []


def _extract_answer_text(result: dict[str, Any]) -> str:
    """Shared text extraction for follow-up gates and advisory coerce."""
    for key in ("answer", "summary", "text", "response", "content", "raw_response", "raw"):
        text = str(result.get(key, "")).strip()
        if text:
            return text
    return ""


def follow_up_answer_gaps(result: dict[str, Any]) -> list[str]:
    """Relaxed quality gate for operator follow-up answers."""
    if _extract_answer_text(result):
        return []
    return ["missing_answer"]


def coerce_consultant_advisory_result(result: dict[str, Any], *, goal: str) -> bool:
    """Map conversational consultant text into minimal structured finding fields."""
    if consultant_finding_gaps(result) == []:
        return False
    text = _extract_answer_text(result)
    if not text:
        return False
    if not str(result.get("topic", "")).strip():
        result["topic"] = (goal or "Advisory")[:120]
    if not str(result.get("summary", "")).strip():
        result["summary"] = text
    recs = _consultant_recommendations(result)
    if len(recs) < 2:
        fillers = ["Review the guidance above.", "Ask a follow-up for specifics."]
        result["recommendations"] = recs + fillers[: 2 - len(recs)]
    if not result.get("confidence"):
        result["confidence"] = 0.6
    return consultant_finding_gaps(result) == []


def consultant_finding_gaps(result: dict[str, Any]) -> list[str]:
    normalize_consultant_lists(result)
    gaps: list[str] = []
    if not str(result.get("topic", "")).strip():
        gaps.append("missing_topic")
    if not str(result.get("summary", "")).strip():
        gaps.append("missing_summary")
    if len(_consultant_recommendations(result)) < 2:
        gaps.append("missing_recommendations")
    confidence = result.get("confidence", 0)
    try:
        confidence_val = float(confidence)
    except (TypeError, ValueError):
        confidence_val = 0.0
    if confidence_val <= 0:
        gaps.append("missing_confidence")
    return gaps


def _consultant_meets_minimum(result: dict[str, Any]) -> bool:
    return not consultant_finding_gaps(result)


def has_planned_tool_calls(result: dict[str, Any]) -> bool:
    """Detect JSON tool plans emitted as text instead of native tool invocations."""
    tool_calls = result.get("tool_calls")
    if isinstance(tool_calls, list) and tool_calls:
        return True
    for key in ("raw", "raw_response"):
        raw = result.get(key)
        if not isinstance(raw, str) or not raw.strip():
            continue
        if '"tool_calls"' in raw and "[" in raw:
            return True
    return False


def preserve_planned_tool_calls(source: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    """Keep tool_calls on validated findings so workers can detect fake tool plans."""
    planned = source.get("tool_calls")
    if isinstance(planned, list) and planned:
        target["tool_calls"] = planned
    return target


def finding_meets_minimum(
    persona: str,
    result: dict[str, Any],
    *,
    schema_name: str | None,
    manifest: EvidenceManifest | None = None,
    upstream_manifests: dict[str, EvidenceManifest] | None = None,
    phase: str | None = None,
    specialist_findings: list[dict[str, Any]] | None = None,
) -> bool:
    if not schema_name:
        return True
    result = normalize_finding_payload(result)
    if "error" in result:
        return False

    if persona == "soc":
        if not str(result.get("summary", "")).strip():
            return False
        if manifest is None:
            return True
        return not soc_evidence_gaps(result, manifest)

    if persona == "intel":
        return bool(str(result.get("summary", "")).strip()) or bool(result.get("iocs"))
    if persona == "hunter":
        return bool(str(result.get("hypothesis", "")).strip()) or bool(str(result.get("summary", "")).strip())
    if persona == "consultant":
        normalize_consultant_lists(result)
        if not _consultant_meets_minimum(result):
            return False
        if phase == "synthesis" and upstream_manifests:
            return not consultant_synthesis_gaps(result, upstream_manifests, specialist_findings)
        return True

    return structured_has_content(result)
