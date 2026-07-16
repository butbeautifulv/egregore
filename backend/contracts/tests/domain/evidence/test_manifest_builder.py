from __future__ import annotations

import pytest

from cys_core.domain.evidence.manifest_builder import (
    build_manifest_from_investigation,
    build_manifest_from_tool_output,
    merge_manifests,
)
from cys_core.domain.evidence.models import DataGap, EvidenceManifest, FieldAvailability, Observation


def _rich_event(uuid: str = "evt-uuid-1") -> dict:
    return {
        "uuid": uuid,
        "subject": {
            "process": {"cmdline": "cmd.exe /c whoami", "name": "cmd.exe", "id": "1234"},
            "account": {"name": "DOMAIN\\alice"},
        },
        "object": {"name": r"\\.\pipe\malicious", "value": "pipe-data"},
        "event_src": {"host": "workstation-1", "ip": "10.0.0.5"},
        "correlation_name": "suspicious_login",
        "time": "2026-01-01T12:00:00Z",
        "text": "Suspicious process execution detected on endpoint",
    }


@pytest.mark.unit
def test_build_manifest_from_investigation_rich_telemetry() -> None:
    manifest = build_manifest_from_investigation(
        {
            "incident": {
                "key": "INC-100",
                "category": "Attack",
                "correlationRuleNames": ["brute_force_login"],
                "targets": [{"name": "srv-1", "addresses": ["10.0.0.1", ""]}],
            },
            "linked_events": {"events": [_rich_event()]},
            "recent_events": {"events": [], "truncated": False},
        }
    )
    assert manifest.telemetry_level == "rich"
    assert manifest.max_confidence == 1.0
    assert len(manifest.observations) >= 5
    assert any(obs.kind == "process" for obs in manifest.observations)


@pytest.mark.unit
def test_build_manifest_sparse_without_cmdline() -> None:
    manifest = build_manifest_from_investigation(
        {
            "incident": {"key": "INC-200", "type": "Undefined"},
            "linked_events": {
                "events": [
                    {
                        "uuid": "e1",
                        "event_src": {"host": "host-a"},
                        "text": "metadata only event",
                    }
                ]
            },
            "recent_events": {"truncated": True},
        },
        include_raw_events=False,
    )
    assert manifest.telemetry_level in {"sparse", "metadata_only"}
    gap_fields = {gap.field for gap in manifest.data_gaps}
    assert "subject.process.cmdline" in gap_fields


@pytest.mark.unit
def test_build_manifest_kata_taa_requires_external_console() -> None:
    manifest = build_manifest_from_investigation(
        {
            "incident": {
                "key": "INC-KATA",
                "type": "hacktoolsdetection",
                "category": "kata_taa",
                "correlationRuleNames": ["malicious_pipe_created"],
            },
            "linked_events": {"events": []},
        }
    )
    assert "kata_taa_console" in manifest.required_external_sources
    assert any(gap.field == "object.name" for gap in manifest.data_gaps)


@pytest.mark.unit
def test_build_manifest_merges_valid_embedded_manifest() -> None:
    embedded = EvidenceManifest(telemetry_level="sparse", max_confidence=0.4)
    manifest = build_manifest_from_investigation(
        {
            "incident": {"key": "INC-300"},
            "evidence_manifest": embedded.model_dump(mode="json"),
            "linked_events": {"events": [_rich_event("evt-merge")]},
        }
    )
    assert manifest.telemetry_level == "rich"
    assert manifest.max_confidence <= 0.4


@pytest.mark.unit
def test_build_manifest_ignores_invalid_embedded_manifest() -> None:
    manifest = build_manifest_from_investigation(
        {
            "incident": {"key": "INC-301"},
            "evidence_manifest": {"telemetry_level": "not-a-level"},
            "linked_events": {"events": []},
        }
    )
    assert isinstance(manifest, EvidenceManifest)


@pytest.mark.unit
def test_build_manifest_walks_list_and_items_shapes() -> None:
    manifest = build_manifest_from_investigation(
        {
            "incident": {},
            "linked_events": [_rich_event("list-shape")],
            "recent_events": {"items": [_rich_event("items-shape")]},
        }
    )
    assert len(manifest.observations) >= 2


@pytest.mark.unit
def test_build_manifest_from_tool_output_investigate_truncated() -> None:
    manifest = build_manifest_from_tool_output(
        "investigate_incident",
        {
            "incident": {"key": "INC-400"},
            "recent_events": {"truncated": True},
        },
    )
    assert manifest is not None
    assert manifest.telemetry_level in {"sparse", "metadata_only"}


@pytest.mark.unit
def test_build_manifest_from_tool_output_search_events() -> None:
    manifest = build_manifest_from_tool_output(
        "search_events",
        {"body": {"events": [_rich_event("search-evt")]}},
    )
    assert manifest is not None
    assert manifest.observations


@pytest.mark.unit
def test_build_manifest_from_tool_output_get_event_by_uuid() -> None:
    manifest = build_manifest_from_tool_output(
        "get_event_by_uuid",
        {"body": _rich_event("single-evt")},
    )
    assert manifest is not None


@pytest.mark.unit
def test_build_manifest_from_tool_output_list_incident_events() -> None:
    manifest = build_manifest_from_tool_output(
        "list_incident_events",
        {"body": {"data": [_rich_event("list-incident")]}},
    )
    assert manifest is not None


@pytest.mark.unit
def test_build_manifest_from_tool_output_unknown_tool() -> None:
    assert build_manifest_from_tool_output("unknown_tool", {}) is None


@pytest.mark.unit
def test_build_manifest_from_tool_output_no_observations() -> None:
    assert build_manifest_from_tool_output("search_events", {"body": {"events": []}}) is None


@pytest.mark.unit
def test_merge_manifests_empty_returns_default() -> None:
    merged = merge_manifests()
    assert merged.telemetry_level == "metadata_only"


@pytest.mark.unit
def test_merge_manifests_combines_observations_and_gaps() -> None:
    left = EvidenceManifest(
        telemetry_level="sparse",
        max_confidence=0.5,
        observations=[
            Observation(
                obs_id="obs:a:1",
                kind="host",
                value="host-a",
                source_tool="siem",
                source_path="events",
            )
        ],
        data_gaps=[DataGap(field="subject.process.cmdline", reason="not_in_siem")],
        field_availability=[
            FieldAvailability(field_path="subject.process.cmdline", present=False, source="incident"),
        ],
        suggested_mitre_techniques=["T1046"],
    )
    right = EvidenceManifest(
        telemetry_level="rich",
        max_confidence=0.8,
        observations=[
            Observation(
                obs_id="obs:b:1",
                kind="ip",
                value="10.0.0.2",
                source_tool="siem",
                source_path="events",
            )
        ],
        field_availability=[
            FieldAvailability(
                field_path="subject.process.cmdline",
                present=True,
                source="linked_events",
                event_uuids=["evt-1"],
            )
        ],
        suggested_mitre_techniques=["T1055"],
        enrichment_sources=["edr"],
        required_external_sources=["kata_taa_console"],
    )
    merged = merge_manifests(left, right)
    assert merged.telemetry_level == "rich"
    assert merged.max_confidence == 0.5
    assert len(merged.observations) == 2
    assert {gap.field for gap in merged.data_gaps} == {"subject.process.cmdline"}
    fa = next(item for item in merged.field_availability if item.field_path == "subject.process.cmdline")
    assert fa.present is True
    assert "evt-1" in fa.event_uuids
    assert merged.suggested_mitre_techniques == ["T1046", "T1055"]
    assert "edr" in merged.enrichment_sources
