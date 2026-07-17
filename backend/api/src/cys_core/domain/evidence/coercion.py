from __future__ import annotations

from typing import Any

from cys_core.domain.evidence.models import DataGap, EvidenceManifest, EvidenceRef


def coerce_evidence_refs(result: dict[str, Any]) -> list[EvidenceRef]:
    refs: list[EvidenceRef] = []
    raw = result.get("evidence") or []
    if not isinstance(raw, list):
        return refs
    for item in raw:
        if isinstance(item, EvidenceRef):
            refs.append(item)
        elif isinstance(item, dict):
            try:
                refs.append(EvidenceRef.model_validate(item))
            except Exception:
                continue
        elif isinstance(item, str) and item.strip():
            refs.append(EvidenceRef(obs_id=item.strip(), excerpt=item.strip()))
    return refs


def coerce_data_gaps(result: dict[str, Any]) -> list[DataGap]:
    gaps: list[DataGap] = []
    raw = result.get("data_gaps") or []
    if not isinstance(raw, list):
        return gaps
    for item in raw:
        if isinstance(item, DataGap):
            gaps.append(item)
        elif isinstance(item, dict):
            try:
                gaps.append(DataGap.model_validate(item))
            except Exception:
                continue
        elif isinstance(item, str) and item.strip():
            gaps.append(DataGap(field=item.strip(), reason="not_in_siem"))
    return gaps


def coerce_sparse_soc_finding(result: dict[str, Any], manifest: EvidenceManifest) -> bool:
    """Merge sparse-SIEM manifest metadata into a SOC finding. Returns True if mutated."""
    if manifest.telemetry_level == "rich":
        return False

    mutated = False
    telemetry = str(result.get("telemetry_level", "")).strip()
    if telemetry != manifest.telemetry_level:
        result["telemetry_level"] = manifest.telemetry_level
        mutated = True

    finding_gaps = coerce_data_gaps(result)
    gap_by_field = {gap.field: gap for gap in finding_gaps}
    for manifest_gap in manifest.data_gaps:
        if manifest_gap.field not in gap_by_field:
            gap_by_field[manifest_gap.field] = manifest_gap
            mutated = True
    if gap_by_field and (mutated or len(gap_by_field) != len(finding_gaps)):
        result["data_gaps"] = [gap.model_dump(mode="json") for gap in gap_by_field.values()]
        mutated = True

    confidence = result.get("confidence", 0)
    try:
        confidence_val = float(confidence)
    except (TypeError, ValueError):
        confidence_val = 0.0
    if confidence_val > manifest.max_confidence:
        result["confidence"] = manifest.max_confidence
        mutated = True

    if mutated:
        result["degraded"] = True
    return mutated
