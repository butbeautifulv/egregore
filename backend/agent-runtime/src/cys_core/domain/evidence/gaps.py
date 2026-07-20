from __future__ import annotations

from typing import Any

from cys_core.domain.evidence.coercion import coerce_data_gaps, coerce_evidence_refs
from cys_core.domain.evidence.models import DataGap, EvidenceManifest
from cys_core.domain.evidence.observation_ids import CREDENTIAL_TECHNIQUE_PREFIXES
from cys_core.domain.evidence.resolver import entity_grounded, extract_entities, observation_supports_ref


def _finding_gap_fields(gaps: list[DataGap]) -> set[str]:
    return {gap.field for gap in gaps}


def _manifest_gap_fields(manifest: EvidenceManifest) -> set[str]:
    return {gap.field for gap in manifest.data_gaps}


def _mitre_requires_credential_fields(techniques: list[str]) -> bool:
    return any(str(t).upper().startswith(prefix) for t in techniques for prefix in CREDENTIAL_TECHNIQUE_PREFIXES)


def _credential_fields_available(manifest: EvidenceManifest) -> bool:
    for fa in manifest.field_availability:
        if not fa.present:
            continue
        if "cmdline" in fa.field_path or "account" in fa.field_path:
            return True
    return False


def soc_evidence_gaps(
    result: dict[str, Any],
    manifest: EvidenceManifest | None,
) -> list[str]:
    if manifest is None:
        return []

    gaps: list[str] = []
    summary = str(result.get("summary", "")).strip()
    if not summary:
        gaps.append("missing_summary")
        return gaps

    refs = coerce_evidence_refs(result)
    sparse = manifest.telemetry_level != "rich"
    finding_gaps = coerce_data_gaps(result)

    if not refs:
        if not sparse or not finding_gaps:
            gaps.append("missing_evidence_refs")

    for ref in refs:
        if not observation_supports_ref(ref, manifest):
            gaps.append(f"invalid_evidence_ref:{ref.obs_id}")

    confidence = result.get("confidence", 0)
    try:
        confidence_val = float(confidence)
    except (TypeError, ValueError):
        confidence_val = 0.0
    if confidence_val > manifest.max_confidence:
        gaps.append("confidence_exceeds_manifest_cap")

    if sparse:
        if not finding_gaps:
            gaps.append("missing_data_gaps")
        else:
            manifest_fields = _manifest_gap_fields(manifest)
            finding_fields = _finding_gap_fields(finding_gaps)
            if manifest_fields and not manifest_fields.issubset(finding_fields):
                gaps.append("incomplete_data_gaps")

    telemetry_level = str(result.get("telemetry_level", "")).strip()
    if telemetry_level and telemetry_level != manifest.telemetry_level:
        gaps.append("telemetry_level_mismatch")

    techniques = result.get("mitre_techniques") or []
    if isinstance(techniques, list) and _mitre_requires_credential_fields(techniques):
        if not _credential_fields_available(manifest):
            gap_fields = _finding_gap_fields(finding_gaps)
            if "subject.process.cmdline" not in gap_fields and "subject.account.name" not in gap_fields:
                gaps.append("ungrounded_mitre_credential_technique")

    for entity_type, value in extract_entities(summary):
        if not entity_grounded(entity_type, value, manifest):
            gaps.append(f"ungrounded_entity:{entity_type}:{value}")

    return list(dict.fromkeys(gaps))


def consultant_synthesis_gaps(
    result: dict[str, Any],
    upstream_manifests: dict[str, EvidenceManifest],
    specialist_findings: list[dict[str, Any]] | None = None,
) -> list[str]:
    if not upstream_manifests:
        return []

    sparse = any(m.telemetry_level != "rich" for m in upstream_manifests.values())
    if not sparse:
        return []

    combined = f"{result.get('topic', '')}\n{result.get('summary', '')}"
    merged = EvidenceManifest()
    for manifest in upstream_manifests.values():
        merged = EvidenceManifest(
            telemetry_level=manifest.telemetry_level,
            observations=[*merged.observations, *manifest.observations],
            field_availability=[*merged.field_availability, *manifest.field_availability],
            data_gaps=[*merged.data_gaps, *manifest.data_gaps],
            max_confidence=min(merged.max_confidence, manifest.max_confidence),
        )

    gaps: list[str] = []
    for entity_type, value in extract_entities(combined):
        if entity_grounded(entity_type, value, merged):
            continue
        backed = False
        for item in specialist_findings or []:
            finding_raw = item.get("finding")
            finding: dict[str, Any] = finding_raw if isinstance(finding_raw, dict) else {}
            for ref in coerce_evidence_refs(finding):
                obs = merged.observation_index().get(ref.obs_id)
                if obs is not None and value.lower() in obs.value.lower():
                    backed = True
                    break
            if backed:
                break
        if not backed:
            gaps.append(f"ungrounded_synthesis_entity:{entity_type}:{value}")

    confidence = result.get("confidence", 0)
    try:
        confidence_val = float(confidence)
    except (TypeError, ValueError):
        confidence_val = 0.0
    max_conf = min((m.max_confidence for m in upstream_manifests.values()), default=1.0)
    if confidence_val > max_conf:
        gaps.append("confidence_exceeds_upstream_cap")

    return list(dict.fromkeys(gaps))
