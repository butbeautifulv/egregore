from __future__ import annotations

from typing import Any

from cys_core.domain.evidence.models import DataGap, EvidenceRef


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
