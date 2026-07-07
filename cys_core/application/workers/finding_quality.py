from __future__ import annotations

from typing import Any

from cys_core.application.workers.evidence_gate import consultant_synthesis_gaps, soc_evidence_gaps
from cys_core.application.workers.tool_execution_tracker import get_merged_manifest, get_persona_manifests
from cys_core.domain.parsing.json_text import parse_json_text


def normalize_finding_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Unwrap common LLM finding envelopes before schema validation."""
    if not isinstance(data, dict) or "error" in data:
        return data

    finding_val = data.get("finding")
    if isinstance(finding_val, dict) and finding_val:
        unwrapped = normalize_finding_payload(finding_val)
        if unwrapped:
            return unwrapped

    for key in ("data", "result", "output"):
        nested = data.get(key)
        if isinstance(nested, dict) and nested:
            unwrapped = normalize_finding_payload(nested)
            if unwrapped and _looks_like_worker_finding(unwrapped):
                return unwrapped

    content_parsed = data.get("content_parsed")
    if isinstance(content_parsed, dict):
        return normalize_finding_payload(content_parsed)

    for key in ("content", "raw_response"):
        raw = data.get(key)
        if isinstance(raw, str) and raw.strip():
            parsed = parse_json_text(raw)
            if isinstance(parsed, dict):
                return normalize_finding_payload(parsed)

    return data


def _looks_like_worker_finding(data: dict[str, Any]) -> bool:
    markers = (
        "summary",
        "topic",
        "hypothesis",
        "iocs",
        "actor_profile",
        "artifacts",
        "identity_asset",
        "cloud_provider",
        "recommendations",
        "severity",
    )
    return any(key in data for key in markers)


def structured_has_content(result: dict[str, Any]) -> bool:
    for value in result.values():
        if isinstance(value, str) and value.strip():
            return True
        if isinstance(value, list) and value:
            return True
        if isinstance(value, (int, float)) and value not in (0, 0.0):
            return True
    return False


def normalize_list_field(data: dict[str, Any], key: str) -> None:
    """Coerce a single string into a one-item list; drop invalid non-list values."""
    if key not in data:
        return
    value = data[key]
    if isinstance(value, str):
        stripped = value.strip()
        data[key] = [stripped] if stripped else []
        return
    if isinstance(value, list):
        data[key] = [str(item).strip() for item in value if str(item).strip()]
        return
    del data[key]


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


def consultant_finding_gaps(result: dict[str, Any]) -> list[str]:
    """Return missing consultant finding fields (empty when quality gate passes)."""
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
    job_id: str | None = None,
    investigation_id: str | None = None,
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
        if not job_id:
            return True
        manifest = get_merged_manifest(job_id)
        return not soc_evidence_gaps(result, manifest)

    if persona == "intel":
        return bool(str(result.get("summary", "")).strip()) or bool(result.get("iocs"))
    if persona == "hunter":
        return bool(str(result.get("hypothesis", "")).strip()) or bool(str(result.get("summary", "")).strip())
    if persona == "consultant":
        normalize_consultant_lists(result)
        if not _consultant_meets_minimum(result):
            return False
        if phase == "synthesis" and investigation_id:
            upstream = get_persona_manifests(investigation_id)
            if upstream:
                return not consultant_synthesis_gaps(result, upstream, specialist_findings)
        return True

    return structured_has_content(result)
