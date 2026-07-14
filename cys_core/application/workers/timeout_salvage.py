from __future__ import annotations

import json
import re
from typing import Any

from bootstrap.settings import get_settings
from cys_core.application.workers.tool_execution_tracker import get_merged_manifest
from cys_core.domain.evidence.models import EvidenceRef

_IOC_PATTERN = re.compile(
    r"\b(?:\d{1,3}\.){3}\d{1,3}\b|[a-f0-9]{32}|[a-f0-9]{40}|[a-f0-9]{64}",
    re.IGNORECASE,
)

_SOC_SUMMARY_TOOLS = ("investigate_incident", "get_incident", "search_events", "list_incident_events")
_INTEL_SUMMARY_TOOLS = ("enrich_ioc", "ti_search_in_category", "playbook_search", "investigate_incident")
_LADDER_BLOCK_MARKERS = (
    "SIEM ladder complete",
    "already completed",
    "SIEM/Veil ladder complete",
    "Emit SocFinding JSON",
    "Emit the persona finding JSON",
)


def _is_ladder_block_output(preview: str) -> bool:
    return any(marker in preview for marker in _LADDER_BLOCK_MARKERS)


def _truncate_summary(text: str) -> str:
    cleaned = " ".join(text.split())
    summary_max = get_settings().timeout_salvage_summary_max
    if len(cleaned) <= summary_max:
        return cleaned
    return cleaned[:summary_max] + "…"


def _summary_from_outputs(tool_outputs: list[tuple[str, str]], preferred: tuple[str, ...]) -> str:
    by_name = {name: preview for name, preview in tool_outputs}
    for tool_name in preferred:
        preview = by_name.get(tool_name, "").strip()
        if preview and not _is_ladder_block_output(preview):
            return _truncate_summary(preview)
    for _name, preview in reversed(tool_outputs):
        cleaned = preview.strip()
        if cleaned and not _is_ladder_block_output(cleaned):
            return _truncate_summary(cleaned)
    return ""


def _extract_iocs(text: str) -> list[str]:
    seen: set[str] = set()
    iocs: list[str] = []
    for match in _IOC_PATTERN.findall(text):
        value = match.strip()
        if value and value not in seen:
            seen.add(value)
            iocs.append(value)
        if len(iocs) >= 20:
            break
    return iocs


def _collect_iocs(tool_outputs: list[tuple[str, str]]) -> list[str]:
    combined = "\n".join(preview for _, preview in tool_outputs)
    return _extract_iocs(combined)


def _manifest_grounded_soc(
    summary: str,
    manifest: Any,
    *,
    salvage_reason: str,
) -> dict[str, Any]:
    evidence = [
        EvidenceRef(obs_id=obs.obs_id, excerpt=obs.value).model_dump()
        for obs in manifest.observations[:8]
    ]
    return {
        "incomplete": True,
        "salvage_reason": salvage_reason,
        "summary": summary,
        "telemetry_level": manifest.telemetry_level,
        "confidence": min(0.3, manifest.max_confidence),
        "evidence": evidence,
        "data_gaps": [gap.model_dump() for gap in manifest.data_gaps],
    }


def build_salvage_finding(
    persona: str,
    tool_outputs: list[tuple[str, str]],
    *,
    job_id: str = "",
    salvage_reason: str = "worker_job_timeout",
) -> dict[str, Any] | None:
    """Build a minimal partial finding from cached tool previews after timeout or recursion."""
    if not tool_outputs:
        return None

    base = {
        "incomplete": True,
        "salvage_reason": salvage_reason,
        "confidence": 0.3,
    }

    if persona == "soc":
        summary = _summary_from_outputs(tool_outputs, _SOC_SUMMARY_TOOLS)
        if not summary:
            return None
        manifest = get_merged_manifest(job_id) if job_id else None
        if manifest is not None and manifest.observations:
            return _manifest_grounded_soc(summary, manifest, salvage_reason=salvage_reason)
        return {**base, "summary": summary}

    if persona == "intel":
        summary = _summary_from_outputs(tool_outputs, _INTEL_SUMMARY_TOOLS)
        iocs = _collect_iocs(tool_outputs)
        if not summary and not iocs:
            return None
        finding: dict[str, Any] = {**base}
        if summary:
            finding["summary"] = summary
        if iocs:
            finding["iocs"] = iocs
        if not finding.get("summary"):
            finding["summary"] = f"Partial TI context salvaged from {len(tool_outputs)} tool(s)."
        return finding

    if persona == "hunter":
        summary = _summary_from_outputs(tool_outputs, _SOC_SUMMARY_TOOLS + _INTEL_SUMMARY_TOOLS)
        if not summary:
            return None
        return {**base, "hypothesis": summary, "summary": summary}

    # Generic fallback for other personas with schema output
    summary = _summary_from_outputs(tool_outputs, _SOC_SUMMARY_TOOLS + _INTEL_SUMMARY_TOOLS)
    if not summary:
        return None
    try:
        parsed = json.loads(tool_outputs[-1][1])
        if isinstance(parsed, dict) and str(parsed.get("summary", "")).strip():
            return {**parsed, **base}
    except (json.JSONDecodeError, TypeError):
        pass
    return {**base, "summary": summary}
