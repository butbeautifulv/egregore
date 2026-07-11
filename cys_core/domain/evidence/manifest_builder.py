from __future__ import annotations

from typing import Any

from cys_core.domain.evidence.incident_mitre import infer_suggested_mitre_techniques
from cys_core.domain.evidence.observation_ids import build_obs_id
from cys_core.domain.evidence.models import (
    DataGap,
    EvidenceManifest,
    FieldAvailability,
    FieldSource,
    Observation,
    ObservationKind,
)

_FORENSIC_FIELD_PATHS: tuple[tuple[str, ObservationKind], ...] = (
    ("subject.process.cmdline", "process"),
    ("object.process.cmdline", "process"),
    ("subject.process.name", "process"),
    ("object.process.name", "process"),
    ("subject.process.id", "pid"),
    ("object.process.id", "pid"),
    ("subject.account.name", "account"),
    ("object.account.name", "account"),
    ("object.name", "pipe"),
    ("object.value", "pipe"),
)

_KATA_TAA_MARKERS = (
    "kata_taa",
    "malicious_pipe_created",
    "hacktoolsdetection",
)

def _get_nested(data: dict[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _walk_events(body: Any) -> list[dict[str, Any]]:
    if isinstance(body, list):
        return [item for item in body if isinstance(item, dict)]
    if not isinstance(body, dict):
        return []
    for key in ("events", "items", "data"):
        items = body.get(key)
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    return []


def _add_observation(
    observations: dict[str, Observation],
    *,
    kind: ObservationKind,
    value: str,
    source_tool: str,
    source_path: str,
    event_uuid: str | None = None,
) -> None:
    text = str(value).strip()
    if not text:
        return
    oid = build_obs_id(kind, text, event_uuid)
    if oid in observations:
        return
    observations[oid] = Observation(
        obs_id=oid,
        kind=kind,
        value=text,
        source_tool=source_tool,
        source_path=source_path,
        event_uuid=event_uuid,
    )


def _scan_event_fields(
    event: dict[str, Any],
    *,
    source_tool: str,
    source: FieldSource,
    observations: dict[str, Observation],
    availability: dict[str, FieldAvailability],
) -> None:
    event_uuid = str(event.get("uuid") or event.get("id") or "").strip() or None
    for field_path, kind in _FORENSIC_FIELD_PATHS:
        value = _get_nested(event, field_path)
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        fa = availability.get(field_path)
        if fa is None:
            fa = FieldAvailability(field_path=field_path, present=False, source=source)
            availability[field_path] = fa
        fa.present = True
        if event_uuid and event_uuid not in fa.event_uuids:
            fa.event_uuids.append(event_uuid)
        _add_observation(
            observations,
            kind=kind,
            value=text,
            source_tool=source_tool,
            source_path=f"{source}.{event_uuid or 'event'}.{field_path}",
            event_uuid=event_uuid,
        )

    for host_key in ("event_src.host", "src.host", "dst.host"):
        host = _get_nested(event, host_key)
        if host:
            _add_observation(
                observations,
                kind="host",
                value=str(host),
                source_tool=source_tool,
                source_path=f"{source}.{event_uuid or 'event'}.{host_key}",
                event_uuid=event_uuid,
            )
    for ip_key in ("event_src.ip", "src.ip", "dst.ip"):
        ip = _get_nested(event, ip_key)
        if ip:
            _add_observation(
                observations,
                kind="ip",
                value=str(ip),
                source_tool=source_tool,
                source_path=f"{source}.{event_uuid or 'event'}.{ip_key}",
                event_uuid=event_uuid,
            )
    correlation = event.get("correlation_name")
    if correlation:
        _add_observation(
            observations,
            kind="correlation_rule",
            value=str(correlation),
            source_tool=source_tool,
            source_path=f"{source}.{event_uuid or 'event'}.correlation_name",
            event_uuid=event_uuid,
        )
    if event.get("time"):
        _add_observation(
            observations,
            kind="timestamp",
            value=str(event["time"]),
            source_tool=source_tool,
            source_path=f"{source}.{event_uuid or 'event'}.time",
            event_uuid=event_uuid,
        )
    if event.get("text"):
        _add_observation(
            observations,
            kind="event_text",
            value=str(event["text"])[:500],
            source_tool=source_tool,
            source_path=f"{source}.{event_uuid or 'event'}.text",
            event_uuid=event_uuid,
        )


def _incident_observations(
    incident_body: dict[str, Any],
    *,
    source_tool: str,
    observations: dict[str, Observation],
) -> list[str]:
    rules: list[str] = []
    correlation_rules = incident_body.get("correlationRuleNames") or []
    if isinstance(correlation_rules, list):
        for rule in correlation_rules:
            text = str(rule).strip()
            if not text:
                continue
            rules.append(text)
            _add_observation(
                observations,
                kind="correlation_rule",
                value=text,
                source_tool=source_tool,
                source_path="incident.correlationRuleNames",
            )
    incident_key = incident_body.get("key")
    if incident_key:
        _add_observation(
            observations,
            kind="incident_key",
            value=str(incident_key),
            source_tool=source_tool,
            source_path="incident.key",
        )
    category = incident_body.get("category")
    if category:
        _add_observation(
            observations,
            kind="category",
            value=str(category),
            source_tool=source_tool,
            source_path="incident.category",
        )
    targets = incident_body.get("targets") or []
    if isinstance(targets, list):
        for idx, target in enumerate(targets):
            if not isinstance(target, dict):
                continue
            name = target.get("name")
            if name:
                _add_observation(
                    observations,
                    kind="host",
                    value=str(name),
                    source_tool=source_tool,
                    source_path=f"incident.targets[{idx}].name",
                )
            for addr in target.get("addresses") or []:
                if addr:
                    _add_observation(
                        observations,
                        kind="ip",
                        value=str(addr),
                        source_tool=source_tool,
                        source_path=f"incident.targets[{idx}].addresses",
                    )
    return rules


def _kata_taa_detected(rules: list[str], incident_body: dict[str, Any]) -> bool:
    corpus = " ".join(rules).lower()
    for marker in _KATA_TAA_MARKERS:
        if marker in corpus:
            return True
    for field in ("category", "type", "name"):
        value = str(incident_body.get(field, "")).lower()
        if any(marker in value for marker in _KATA_TAA_MARKERS):
            return True
    return False


def _finalize_manifest(
    observations: dict[str, Observation],
    availability: dict[str, FieldAvailability],
    *,
    rules: list[str],
    incident_body: dict[str, Any],
    include_raw_events: bool,
    recent_truncated: bool,
) -> EvidenceManifest:
    has_cmdline = any(
        fa.present for fp, fa in availability.items() if "cmdline" in fp or "process.name" in fp
    )
    has_account = any(fa.present for fp, fa in availability.items() if "account" in fp)
    has_pipe = availability.get("object.name", FieldAvailability(field_path="object.name", present=False)).present
    has_pid = any(fa.present for fp, fa in availability.items() if fp.endswith(".id"))
    kata_taa = _kata_taa_detected(rules, incident_body)

    data_gaps: list[DataGap] = []
    if not has_cmdline:
        data_gaps.append(
            DataGap(
                field="subject.process.cmdline",
                reason="not_in_siem" if include_raw_events else "not_selected",
                remediation="Request full event telemetry or check EDR/KATA console for process details.",
            )
        )
    if not has_account:
        data_gaps.append(
            DataGap(
                field="subject.account.name",
                reason="not_in_siem",
                remediation="Collect authentication audit logs or endpoint telemetry for account context.",
            )
        )
    if kata_taa and not has_pipe:
        data_gaps.append(
            DataGap(
                field="object.name",
                reason="vendor_api_unavailable",
                remediation="Open KATA console for pipe name and payload details (TAA API enrichment unavailable).",
            )
        )

    required_external: list[str] = []
    if kata_taa and (not has_cmdline or not has_pipe):
        required_external.append("kata_taa_console")

    if not observations:
        telemetry_level = "metadata_only"
        max_confidence = 0.3
    elif kata_taa and not has_cmdline:
        telemetry_level = "sparse"
        max_confidence = 0.5
    elif not has_cmdline and not has_account:
        telemetry_level = "sparse"
        max_confidence = 0.5
    elif recent_truncated and not include_raw_events:
        telemetry_level = "sparse"
        max_confidence = 0.5
    else:
        telemetry_level = "rich"
        max_confidence = 1.0

    for fp, _kind in _FORENSIC_FIELD_PATHS:
        if fp not in availability:
            availability[fp] = FieldAvailability(field_path=fp, present=False, source="incident")

    suggested_mitre = infer_suggested_mitre_techniques(
        incident_type=str(incident_body.get("type", "")),
        incident_name=str(incident_body.get("name", "")),
        correlation_rules=rules,
    )

    return EvidenceManifest(
        telemetry_level=telemetry_level,
        enrichment_sources=["siem"],
        required_external_sources=required_external,
        observations=list(observations.values()),
        field_availability=list(availability.values()),
        data_gaps=data_gaps,
        suggested_mitre_techniques=suggested_mitre,
        max_confidence=max_confidence,
    )


def build_manifest_from_investigation(
    payload: dict[str, Any],
    *,
    source_tool: str = "investigate_incident",
    include_raw_events: bool = True,
) -> EvidenceManifest:
    observations: dict[str, Observation] = {}
    availability: dict[str, FieldAvailability] = {}

    incident_body = payload.get("incident")
    if not isinstance(incident_body, dict):
        incident_body = {}

    rules = _incident_observations(incident_body, source_tool=source_tool, observations=observations)

    linked = payload.get("linked_events")
    for event in _walk_events(linked):
        _scan_event_fields(
            event,
            source_tool=source_tool,
            source="linked_events",
            observations=observations,
            availability=availability,
        )

    recent = payload.get("recent_events")
    recent_truncated = isinstance(recent, dict) and bool(recent.get("truncated"))
    if include_raw_events:
        for event in _walk_events(recent):
            _scan_event_fields(
                event,
                source_tool=source_tool,
                source="recent_events",
                observations=observations,
                availability=availability,
            )

    existing_manifest = payload.get("evidence_manifest")
    if isinstance(existing_manifest, dict):
        try:
            embedded = EvidenceManifest.model_validate(existing_manifest)
            return merge_manifests(
                embedded,
                _finalize_manifest(
                    observations,
                    availability,
                    rules=rules,
                    incident_body=incident_body,
                    include_raw_events=include_raw_events,
                    recent_truncated=recent_truncated,
                ),
            )
        except Exception:
            pass

    return _finalize_manifest(
        observations,
        availability,
        rules=rules,
        incident_body=incident_body,
        include_raw_events=include_raw_events,
        recent_truncated=recent_truncated,
    )


def build_manifest_from_tool_output(
    tool_name: str,
    payload: dict[str, Any],
) -> EvidenceManifest | None:
    if tool_name == "investigate_incident":
        include_raw = True
        recent = payload.get("recent_events")
        if isinstance(recent, dict) and recent.get("truncated") and "events" not in recent:
            include_raw = False
        return build_manifest_from_investigation(payload, source_tool=tool_name, include_raw_events=include_raw)

    if tool_name in {"search_events", "get_event_by_uuid", "list_incident_events"}:
        observations: dict[str, Observation] = {}
        availability: dict[str, FieldAvailability] = {}
        body = payload.get("body", payload)
        events = _walk_events(body)
        if tool_name == "get_event_by_uuid" and isinstance(body, dict) and not events:
            events = [body]
        source = "search_events" if tool_name == "search_events" else "event_detail"
        for event in events:
            _scan_event_fields(
                event,
                source_tool=tool_name,
                source=source,  # type: ignore[arg-type]
                observations=observations,
                availability=availability,
            )
        if not observations:
            return None
        return _finalize_manifest(
            observations,
            availability,
            rules=[],
            incident_body={},
            include_raw_events=True,
            recent_truncated=False,
        )
    return None


def merge_manifests(*manifests: EvidenceManifest) -> EvidenceManifest:
    if not manifests:
        return EvidenceManifest()
    obs: dict[str, Observation] = {}
    availability: dict[str, FieldAvailability] = {}
    data_gaps: dict[str, DataGap] = {}
    required: set[str] = set()
    enrichment: set[str] = set()
    max_confidence = 1.0
    telemetry_rank = {"metadata_only": 0, "sparse": 1, "rich": 2}
    telemetry_level = "metadata_only"
    suggested_mitre: list[str] = []
    seen_mitre: set[str] = set()

    for manifest in manifests:
        for observation in manifest.observations:
            obs[observation.obs_id] = observation
        for fa in manifest.field_availability:
            existing = availability.get(fa.field_path)
            if existing is None:
                availability[fa.field_path] = fa.model_copy()
            else:
                existing.present = existing.present or fa.present
                for uuid in fa.event_uuids:
                    if uuid not in existing.event_uuids:
                        existing.event_uuids.append(uuid)
        for gap in manifest.data_gaps:
            data_gaps[gap.field] = gap
        required.update(manifest.required_external_sources)
        enrichment.update(manifest.enrichment_sources)
        max_confidence = min(max_confidence, manifest.max_confidence)
        if telemetry_rank[manifest.telemetry_level] > telemetry_rank[telemetry_level]:
            telemetry_level = manifest.telemetry_level
        for tid in manifest.suggested_mitre_techniques:
            if tid not in seen_mitre:
                seen_mitre.add(tid)
                suggested_mitre.append(tid)

    return EvidenceManifest(
        telemetry_level=telemetry_level,  # type: ignore[arg-type]
        enrichment_sources=sorted(enrichment) or ["siem"],
        required_external_sources=sorted(required),
        observations=list(obs.values()),
        field_availability=list(availability.values()),
        data_gaps=list(data_gaps.values()),
        suggested_mitre_techniques=suggested_mitre,
        max_confidence=max_confidence,
    )
