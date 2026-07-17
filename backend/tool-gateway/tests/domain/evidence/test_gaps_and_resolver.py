from __future__ import annotations

import pytest

from cys_core.domain.evidence.gaps import consultant_synthesis_gaps, soc_evidence_gaps
from cys_core.domain.evidence.models import DataGap, EvidenceManifest, EvidenceRef, FieldAvailability, Observation
from cys_core.domain.evidence.resolver import (
    entity_grounded,
    excerpt_matches,
    extract_entities,
    observation_supports_ref,
    resolve_observation,
)


def _manifest_with_obs() -> EvidenceManifest:
    return EvidenceManifest(
        telemetry_level="sparse",
        max_confidence=0.6,
        data_gaps=[
            DataGap(field="subject.process.cmdline", reason="not_in_siem"),
            DataGap(field="subject.account.name", reason="not_in_siem"),
        ],
        observations=[
            Observation(
                obs_id="obs:evt:abc123:process:cmd.exe",
                kind="process",
                value="cmd.exe /c whoami",
                source_tool="siem",
                source_path="events",
                event_uuid="abc123",
            ),
            Observation(
                obs_id="obs:evt:abc123:account:domain_alice",
                kind="account",
                value="DOMAIN\\alice",
                source_tool="siem",
                source_path="events",
                event_uuid="abc123",
            ),
        ],
        field_availability=[
            FieldAvailability(
                field_path="subject.account.name",
                present=True,
                source="linked_events",
            )
        ],
    )


@pytest.mark.unit
def test_soc_evidence_gaps_none_manifest() -> None:
    assert soc_evidence_gaps({"summary": "x"}, None) == []


@pytest.mark.unit
def test_soc_evidence_gaps_missing_summary_short_circuits() -> None:
    manifest = _manifest_with_obs()
    assert soc_evidence_gaps({}, manifest) == ["missing_summary"]


@pytest.mark.unit
def test_soc_evidence_gaps_reports_invalid_ref_and_confidence() -> None:
    manifest = _manifest_with_obs()
    gaps = soc_evidence_gaps(
        {
            "summary": "cmd.exe on host",
            "confidence": 0.9,
            "telemetry_level": "rich",
            "evidence": [{"obs_id": "obs:missing", "excerpt": "nope"}],
        },
        manifest,
    )
    assert "invalid_evidence_ref:obs:missing" in gaps
    assert "confidence_exceeds_manifest_cap" in gaps
    assert "telemetry_level_mismatch" in gaps


@pytest.mark.unit
def test_soc_evidence_gaps_sparse_requires_data_gaps() -> None:
    manifest = _manifest_with_obs()
    gaps = soc_evidence_gaps({"summary": "activity"}, manifest)
    assert "missing_evidence_refs" in gaps
    assert "missing_data_gaps" in gaps


@pytest.mark.unit
def test_soc_evidence_gaps_incomplete_data_gaps_and_mitre() -> None:
    manifest = _manifest_with_obs()
    gaps = soc_evidence_gaps(
        {
            "summary": "cmd.exe executed",
            "confidence": 0.4,
            "telemetry_level": "sparse",
            "data_gaps": [{"field": "subject.process.cmdline", "reason": "not_in_siem"}],
            "mitre_techniques": ["T1003.001"],
            "evidence": [{"obs_id": "obs:evt:abc123:process:cmd.exe", "excerpt": "cmd.exe"}],
        },
        manifest,
    )
    assert "incomplete_data_gaps" in gaps


@pytest.mark.unit
def test_consultant_synthesis_gaps_empty_upstream() -> None:
    assert consultant_synthesis_gaps({"topic": "t", "summary": "s"}, {}) == []


@pytest.mark.unit
def test_consultant_synthesis_gaps_rich_upstream_skipped() -> None:
    manifest = EvidenceManifest(telemetry_level="rich", max_confidence=1.0)
    assert consultant_synthesis_gaps({"topic": "t", "summary": "s"}, {"soc": manifest}) == []


@pytest.mark.unit
def test_consultant_synthesis_gaps_ungrounded_entity_and_confidence() -> None:
    manifest = EvidenceManifest(telemetry_level="sparse", max_confidence=0.5)
    gaps = consultant_synthesis_gaps(
        {"topic": "Wrap", "summary": "Unknown pipe \\\\.\\pipe\\evil", "confidence": 0.9},
        {"soc": manifest},
        specialist_findings=[],
    )
    assert any(gap.startswith("ungrounded_synthesis_entity:") for gap in gaps)
    assert "confidence_exceeds_upstream_cap" in gaps


@pytest.mark.unit
def test_consultant_synthesis_gaps_backed_by_specialist_finding() -> None:
    manifest = EvidenceManifest(
        telemetry_level="sparse",
        max_confidence=0.6,
        observations=[
            Observation(
                obs_id="obs:evt:1:pipe:evil",
                kind="pipe",
                value=r"\\.\pipe\evil",
                source_tool="siem",
                source_path="events",
            )
        ],
    )
    gaps = consultant_synthesis_gaps(
        {"topic": "Wrap", "summary": "pipe evil activity", "confidence": 0.5},
        {"soc": manifest},
        specialist_findings=[
            {"finding": {"evidence": [{"obs_id": "obs:evt:1:pipe:evil", "excerpt": "evil"}]}}
        ],
    )
    assert gaps == []


@pytest.mark.unit
def test_resolve_observation_slug_and_uuid_fragment() -> None:
    manifest = _manifest_with_obs()
    ref = EvidenceRef(obs_id="obs:evt:abc:process:cmd.exe", excerpt="whoami")
    obs = resolve_observation(ref, manifest)
    assert obs is not None
    assert observation_supports_ref(ref, manifest) is True


@pytest.mark.unit
def test_resolve_observation_excerpt_fallback() -> None:
    manifest = _manifest_with_obs()
    ref = EvidenceRef(obs_id="obs:process:whoami", excerpt="whoami")
    assert resolve_observation(ref, manifest) is not None


@pytest.mark.unit
def test_excerpt_matches_empty_excerpt() -> None:
    obs = _manifest_with_obs().observations[0]
    assert excerpt_matches(EvidenceRef(obs_id=obs.obs_id, excerpt=""), obs) is True


@pytest.mark.unit
def test_extract_entities_and_entity_grounded() -> None:
    summary = "Process malware.exe pid 4321 on \\\\.\\pipe\\test for DOMAIN\\bob"
    entities = extract_entities(summary)
    assert ("process", "malware.exe") in entities
    assert ("pid", "4321") in entities
    manifest = EvidenceManifest(
        observations=[
            Observation(
                obs_id="obs:process:malware.exe",
                kind="process",
                value="malware.exe",
                source_tool="siem",
                source_path="events",
            )
        ]
    )
    assert entity_grounded("process", "malware.exe", manifest) is True
    assert entity_grounded("pipe", "evil", manifest) is False
