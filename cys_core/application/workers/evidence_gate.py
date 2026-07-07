from __future__ import annotations

import re
from typing import Any

from cys_core.domain.evidence.models import DataGap, EvidenceManifest, EvidenceRef, Observation

_PROCESS_ENTITY = re.compile(r"\b([A-Za-z0-9_.-]+\.exe)\b", re.I)
_PID_ENTITY = re.compile(r"\bpid\s*[:=]?\s*(\d+)\b", re.I)
_PIPE_ENTITY = re.compile(r"(\\\\\.\\pipe\\[^\s\"']+|pipe\\[^\s\"']+)", re.I)
_ACCOUNT_ENTITY = re.compile(r"\b([A-Za-z0-9_.-]+\\[A-Za-z0-9_.$-]+)\b")
_CREDENTIAL_TECHNIQUE_PREFIXES = ("T1003",)


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^\w.\-]+", "_", value.strip().lower())
    return cleaned[:80] or "unknown"


def _parse_obs_id(obs_id: str) -> tuple[str | None, str | None, str]:
    parts = obs_id.split(":")
    if len(parts) < 3 or parts[0] != "obs":
        return None, None, ""
    if parts[1] == "evt" and len(parts) >= 5:
        return parts[2], parts[3], ":".join(parts[4:])
    return None, parts[1], ":".join(parts[2:])


def _uuid_fragment_matches(ref_uuid: str, actual_uuid: str | None) -> bool:
    if not actual_uuid:
        return False
    ref = ref_uuid.strip().lower()
    actual = actual_uuid.strip().lower()
    if ref == actual:
        return True
    # Models often truncate leading UUID segments when copying obs_id.
    if len(ref) >= 8 and (actual.endswith(ref) or ref in actual):
        return True
    return False


def _excerpt_matches(ref: EvidenceRef, obs: Observation) -> bool:
    if not ref.excerpt:
        return True
    excerpt = ref.excerpt.strip().lower()
    value = obs.value.strip().lower()
    return excerpt == value or excerpt in value or value in excerpt


def _resolve_observation(ref: EvidenceRef, manifest: EvidenceManifest) -> Observation | None:
    idx = manifest.observation_index()
    exact = idx.get(ref.obs_id)
    if exact is not None:
        return exact

    ref_evt, ref_kind, ref_slug = _parse_obs_id(ref.obs_id)
    candidates: list[Observation] = []
    for candidate in manifest.observations:
        if ref_kind and candidate.kind != ref_kind:
            continue
        _, _, cand_slug = _parse_obs_id(candidate.obs_id)
        slug_match = bool(
            ref_slug
            and (
                ref_slug == _slug(candidate.value)
                or ref_slug == cand_slug
                or ref_slug in candidate.obs_id
            )
        )
        if not slug_match:
            continue
        evt_uuid, _, _ = _parse_obs_id(candidate.obs_id)
        uuid_match = (
            not ref_evt
            or _uuid_fragment_matches(ref_evt, candidate.event_uuid)
            or _uuid_fragment_matches(ref_evt, evt_uuid)
        )
        if uuid_match:
            candidates.append(candidate)

    if len(candidates) == 1:
        return candidates[0]

    if ref.excerpt:
        excerpt = ref.excerpt.strip().lower()
        for candidate in candidates or manifest.observations:
            val = candidate.value.strip().lower()
            if excerpt == val or excerpt in val or val in excerpt:
                return candidate
    return None


def _coerce_evidence_refs(result: dict[str, Any]) -> list[EvidenceRef]:
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


def _coerce_data_gaps(result: dict[str, Any]) -> list[DataGap]:
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


def _ref_matches_observation(ref: EvidenceRef, manifest: EvidenceManifest) -> bool:
    obs = _resolve_observation(ref, manifest)
    if obs is None:
        return False
    return _excerpt_matches(ref, obs)


def _manifest_gap_fields(manifest: EvidenceManifest) -> set[str]:
    return {gap.field for gap in manifest.data_gaps}


def _finding_gap_fields(gaps: list[DataGap]) -> set[str]:
    return {gap.field for gap in gaps}


def _extract_entities(summary: str) -> list[tuple[str, str]]:
    entities: list[tuple[str, str]] = []
    for match in _PROCESS_ENTITY.finditer(summary):
        entities.append(("process", match.group(1)))
    for match in _PID_ENTITY.finditer(summary):
        entities.append(("pid", match.group(1)))
    for match in _PIPE_ENTITY.finditer(summary):
        entities.append(("pipe", match.group(1)))
    for match in _ACCOUNT_ENTITY.finditer(summary):
        entities.append(("account", match.group(1)))
    return entities


def _entity_grounded(entity_type: str, value: str, manifest: EvidenceManifest) -> bool:
    needle = value.lower()
    for obs in manifest.observations:
        if obs.kind == entity_type and needle in obs.value.lower():
            return True
        if entity_type == "process" and obs.kind == "process" and needle in obs.value.lower():
            return True
        if entity_type == "pid" and obs.kind == "pid" and needle in obs.value.lower():
            return True
        if entity_type == "pipe" and obs.kind == "pipe" and needle in obs.value.lower():
            return True
        if entity_type == "account" and obs.kind == "account" and needle in obs.value.lower():
            return True
    return False


def _mitre_requires_credential_fields(techniques: list[str]) -> bool:
    return any(str(t).upper().startswith(prefix) for t in techniques for prefix in _CREDENTIAL_TECHNIQUE_PREFIXES)


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

    refs = _coerce_evidence_refs(result)
    if not refs:
        gaps.append("missing_evidence_refs")

    for ref in refs:
        if not _ref_matches_observation(ref, manifest):
            gaps.append(f"invalid_evidence_ref:{ref.obs_id}")

    confidence = result.get("confidence", 0)
    try:
        confidence_val = float(confidence)
    except (TypeError, ValueError):
        confidence_val = 0.0
    if confidence_val > manifest.max_confidence:
        gaps.append("confidence_exceeds_manifest_cap")

    finding_gaps = _coerce_data_gaps(result)
    if manifest.telemetry_level != "rich":
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

    for entity_type, value in _extract_entities(summary):
        if not _entity_grounded(entity_type, value, manifest):
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
    for entity_type, value in _extract_entities(combined):
        if _entity_grounded(entity_type, value, merged):
            continue
        backed = False
        for item in specialist_findings or []:
            finding = item.get("finding") if isinstance(item.get("finding"), dict) else {}
            for ref in _coerce_evidence_refs(finding):
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
