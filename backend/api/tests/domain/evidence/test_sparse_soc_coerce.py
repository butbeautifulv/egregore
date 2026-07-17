from __future__ import annotations

import pytest

from cys_core.domain.evidence.coercion import coerce_sparse_soc_finding
from cys_core.domain.evidence.gaps import soc_evidence_gaps
from cys_core.domain.evidence.models import DataGap, EvidenceManifest, Observation


def _sparse_manifest() -> EvidenceManifest:
    return EvidenceManifest(
        telemetry_level="sparse",
        max_confidence=0.6,
        data_gaps=[
            DataGap(field="subject.process.cmdline", reason="not_in_siem"),
            DataGap(field="subject.account.name", reason="not_in_siem"),
        ],
        observations=[
            Observation(
                obs_id="obs:evt:abc",
                kind="event_text",
                value="suspicious activity",
                source_tool="siem",
                source_path="events",
            )
        ],
    )


@pytest.mark.unit
def test_coerce_sparse_soc_finding_fills_gaps_and_telemetry() -> None:
    manifest = _sparse_manifest()
    finding = {
        "summary": "Suspicious activity on host-1",
        "telemetry_level": "rich",
        "confidence": 0.9,
        "evidence": [{"obs_id": "obs:evt:abc", "excerpt": "suspicious activity"}],
    }
    assert coerce_sparse_soc_finding(finding, manifest) is True
    assert finding["telemetry_level"] == "sparse"
    assert finding["confidence"] == 0.6
    assert finding["degraded"] is True
    fields = {gap["field"] for gap in finding["data_gaps"]}
    assert fields == {"subject.process.cmdline", "subject.account.name"}
    assert soc_evidence_gaps(finding, manifest) == []


@pytest.mark.unit
def test_coerce_sparse_soc_finding_does_not_mask_invalid_evidence_ref() -> None:
    manifest = _sparse_manifest()
    finding = {
        "summary": "Suspicious activity on host-1",
        "telemetry_level": "sparse",
        "confidence": 0.5,
        "data_gaps": [gap.model_dump(mode="json") for gap in manifest.data_gaps],
        "evidence": [{"obs_id": "obs:evt:missing", "excerpt": "nope"}],
    }
    coerce_sparse_soc_finding(finding, manifest)
    assert "invalid_evidence_ref:obs:evt:missing" in soc_evidence_gaps(finding, manifest)


@pytest.mark.unit
def test_coerce_sparse_soc_finding_noop_on_rich_manifest() -> None:
    manifest = EvidenceManifest(telemetry_level="rich", max_confidence=1.0)
    finding = {"summary": "ok", "telemetry_level": "sparse", "confidence": 0.9}
    assert coerce_sparse_soc_finding(finding, manifest) is False
    assert finding["telemetry_level"] == "sparse"
    assert "degraded" not in finding


@pytest.mark.unit
def test_coerce_sparse_soc_finding_marks_degraded_on_mutation() -> None:
    manifest = _sparse_manifest()
    finding = {
        "summary": "Suspicious activity",
        "telemetry_level": "sparse",
        "confidence": 0.5,
        "data_gaps": [manifest.data_gaps[0].model_dump(mode="json")],
        "evidence": [{"obs_id": "obs:evt:abc", "excerpt": "suspicious activity"}],
    }
    assert coerce_sparse_soc_finding(finding, manifest) is True
    assert finding["degraded"] is True
