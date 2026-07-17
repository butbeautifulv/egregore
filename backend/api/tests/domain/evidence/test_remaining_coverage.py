from __future__ import annotations

import pytest

from cys_core.domain.evidence.gaps import consultant_synthesis_gaps, soc_evidence_gaps
from cys_core.domain.evidence.manifest_builder import build_manifest_from_investigation
from cys_core.domain.evidence.models import DataGap, EvidenceManifest, EvidenceRef, FieldAvailability, Observation
from cys_core.domain.evidence.resolver import resolve_observation


def _sparse_manifest() -> EvidenceManifest:
    return EvidenceManifest(
        telemetry_level="sparse",
        max_confidence=0.6,
        data_gaps=[
            DataGap(field="subject.process.cmdline", reason="not_in_siem"),
            DataGap(field="subject.account.name", reason="not_in_siem"),
        ],
        field_availability=[
            FieldAvailability(field_path="subject.process.cmdline", present=False, source="incident"),
        ],
        observations=[
            Observation(
                obs_id="obs:evt:abc123:process:cmd.exe",
                kind="process",
                value="cmd.exe",
                source_tool="siem",
                source_path="events",
                event_uuid="abc123",
            )
        ],
    )


@pytest.mark.unit
def test_soc_evidence_gaps_ungrounded_mitre_without_credential_gaps() -> None:
    manifest = EvidenceManifest(
        telemetry_level="sparse",
        max_confidence=0.6,
        field_availability=[
            FieldAvailability(field_path="subject.account.name", present=False, source="incident"),
        ],
        observations=[],
    )
    gaps = soc_evidence_gaps(
        {
            "summary": "Credential dumping suspected",
            "confidence": 0.4,
            "telemetry_level": "sparse",
            "data_gaps": [],
            "mitre_techniques": ["T1003"],
        },
        manifest,
    )
    assert "ungrounded_mitre_credential_technique" in gaps


@pytest.mark.unit
def test_soc_evidence_gaps_ungrounded_process_entity() -> None:
    manifest = _sparse_manifest()
    gaps = soc_evidence_gaps(
        {
            "summary": "Detected evil.exe on host",
            "confidence": 0.4,
            "telemetry_level": "sparse",
            "data_gaps": [gap.model_dump(mode="json") for gap in manifest.data_gaps],
            "evidence": [{"obs_id": "obs:evt:abc123:process:cmd.exe", "excerpt": "cmd.exe"}],
        },
        manifest,
    )
    assert any(gap.startswith("ungrounded_entity:process:") for gap in gaps)


@pytest.mark.unit
def test_soc_evidence_gaps_credential_fields_available_skips_mitre_gap() -> None:
    manifest = EvidenceManifest(
        telemetry_level="sparse",
        max_confidence=0.6,
        field_availability=[
            FieldAvailability(field_path="subject.account.name", present=True, source="linked_events"),
        ],
        observations=[],
    )
    gaps = soc_evidence_gaps(
        {
            "summary": "Credential access",
            "confidence": 0.4,
            "telemetry_level": "sparse",
            "data_gaps": [{"field": "subject.process.cmdline", "reason": "not_in_siem"}],
            "mitre_techniques": ["T1003"],
        },
        manifest,
    )
    assert "ungrounded_mitre_credential_technique" not in gaps


@pytest.mark.unit
def test_consultant_synthesis_gaps_invalid_confidence_type() -> None:
    manifest = EvidenceManifest(telemetry_level="sparse", max_confidence=0.5)
    gaps = consultant_synthesis_gaps(
        {"topic": "Wrap", "summary": "summary only", "confidence": "bad"},
        {"soc": manifest},
    )
    assert "confidence_exceeds_upstream_cap" not in gaps


@pytest.mark.unit
def test_consultant_synthesis_gaps_specialist_backing_loop() -> None:
    manifest = EvidenceManifest(
        telemetry_level="sparse",
        max_confidence=0.6,
        observations=[
            Observation(
                obs_id="obs:evt:9:host:alpha",
                kind="host",
                value="alpha-host",
                source_tool="siem",
                source_path="events",
            )
        ],
    )
    gaps = consultant_synthesis_gaps(
        {"topic": "Wrap", "summary": "alpha-host seen in activity", "confidence": 0.5},
        {"soc": manifest},
        specialist_findings=[
            {
                "finding": {
                    "evidence": [{"obs_id": "obs:evt:9:host:alpha", "excerpt": "alpha-host"}],
                }
            }
        ],
    )
    assert gaps == []


@pytest.mark.unit
def test_manifest_builder_skips_empty_values_and_duplicate_obs() -> None:
    manifest = build_manifest_from_investigation(
        {
            "incident": {
                "correlationRuleNames": ["", "valid-rule"],
                "targets": ["not-a-dict", {"addresses": ["10.0.0.2"]}],
                "type": "kata_taa_scan",
            },
            "linked_events": {
                "events": [
                    {
                        "uuid": "dup-evt",
                        "subject": {"process": {"cmdline": "   ", "name": "cmd.exe"}},
                        "text": "first",
                    },
                    {
                        "uuid": "dup-evt",
                        "subject": {"process": {"name": "cmd.exe"}},
                        "text": "second",
                    },
                ]
            },
            "recent_events": {"truncated": True, "events": []},
        },
        include_raw_events=False,
    )
    assert manifest.telemetry_level in {"sparse", "metadata_only"}
    assert any(obs.kind == "correlation_rule" and obs.value == "valid-rule" for obs in manifest.observations)


@pytest.mark.unit
def test_manifest_builder_metadata_only_without_events() -> None:
    manifest = build_manifest_from_investigation({"incident": "not-a-dict"})
    assert manifest.telemetry_level == "metadata_only"
    assert manifest.max_confidence == 0.3


@pytest.mark.unit
def test_resolve_observation_uuid_fragment() -> None:
    manifest = EvidenceManifest(
        observations=[
            Observation(
                obs_id="obs:evt:full-uuid-1234:pid:4321",
                kind="pid",
                value="4321",
                source_tool="siem",
                source_path="events",
                event_uuid="full-uuid-1234",
            ),
        ]
    )
    ref = EvidenceRef(obs_id="obs:evt:uuid-1234:pid:4321", excerpt="4321")
    assert resolve_observation(ref, manifest) is not None
