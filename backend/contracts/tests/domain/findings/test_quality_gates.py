from __future__ import annotations

import pytest

from cys_core.domain.evidence.gaps import consultant_synthesis_gaps
from cys_core.domain.evidence.models import DataGap, EvidenceManifest, Observation
from cys_core.domain.findings.quality_gates import (
    coerce_consultant_advisory_result,
    consultant_finding_gaps,
    finding_meets_minimum,
    follow_up_answer_gaps,
    has_planned_tool_calls,
    normalize_consultant_lists,
    preserve_planned_tool_calls,
)


def _sparse_manifest() -> EvidenceManifest:
    return EvidenceManifest(
        telemetry_level="sparse",
        max_confidence=0.6,
        data_gaps=[DataGap(field="subject.process.cmdline", reason="not_in_siem")],
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
def test_follow_up_answer_gaps_requires_text() -> None:
    assert follow_up_answer_gaps({}) == ["missing_answer"]
    assert follow_up_answer_gaps({"summary": "answer text"}) == []


@pytest.mark.unit
def test_normalize_consultant_lists_copies_recommended_actions() -> None:
    result = {"recommended_actions": "Enable MFA"}
    normalize_consultant_lists(result)
    assert result["recommendations"] == ["Enable MFA"]


@pytest.mark.unit
def test_consultant_finding_gaps_reports_missing_fields() -> None:
    gaps = consultant_finding_gaps({})
    assert "missing_topic" in gaps
    assert "missing_summary" in gaps
    assert "missing_recommendations" in gaps
    assert "missing_confidence" in gaps


@pytest.mark.unit
def test_coerce_consultant_advisory_result_fills_minimum_fields() -> None:
    result = {"raw": "Use network segmentation and MFA."}
    assert coerce_consultant_advisory_result(result, goal="Hardening") is True
    assert consultant_finding_gaps(result) == []
    assert result["topic"] == "Hardening"
    assert "segmentation" in result["summary"]


@pytest.mark.unit
def test_has_planned_tool_calls_detects_list_and_raw_json() -> None:
    assert has_planned_tool_calls({"tool_calls": [{"name": "search"}]}) is True
    assert has_planned_tool_calls({"raw": '{"tool_calls": [{"name": "x"}]}'}) is True
    assert has_planned_tool_calls({"summary": "no tools"}) is False


@pytest.mark.unit
def test_preserve_planned_tool_calls_copies_list() -> None:
    source = {"tool_calls": [{"name": "search"}]}
    target: dict[str, object] = {}
    preserve_planned_tool_calls(source, target)
    assert target["tool_calls"] == [{"name": "search"}]


@pytest.mark.unit
def test_finding_meets_minimum_without_schema() -> None:
    assert finding_meets_minimum("soc", {}, schema_name=None) is True


@pytest.mark.unit
def test_finding_meets_minimum_soc_with_manifest() -> None:
    manifest = _sparse_manifest()
    finding = {
        "summary": "Suspicious login",
        "telemetry_level": "sparse",
        "confidence": 0.5,
        "data_gaps": [gap.model_dump(mode="json") for gap in manifest.data_gaps],
        "evidence": [{"obs_id": "obs:evt:abc", "excerpt": "suspicious activity"}],
    }
    assert finding_meets_minimum("soc", finding, schema_name="SocFinding", manifest=manifest) is True


@pytest.mark.unit
def test_finding_meets_minimum_intel_accepts_iocs() -> None:
    assert finding_meets_minimum("intel", {"iocs": ["10.0.0.1"]}, schema_name="IntelFinding") is True


@pytest.mark.unit
def test_finding_meets_minimum_hunter_accepts_hypothesis() -> None:
    assert finding_meets_minimum("hunter", {"hypothesis": "lateral movement"}, schema_name="HunterFinding") is True


@pytest.mark.unit
def test_finding_meets_minimum_consultant_synthesis_checks_upstream() -> None:
    manifest = _sparse_manifest()
    result = {
        "topic": "Wrap-up",
        "summary": "No new entities beyond evidence.",
        "recommendations": ["Review alerts", "Tune detections"],
        "confidence": 0.5,
    }
    gaps = consultant_synthesis_gaps(result, {"soc": manifest}, specialist_findings=[])
    assert finding_meets_minimum(
        "consultant",
        result,
        schema_name="ConsultantFinding",
        upstream_manifests={"soc": manifest},
        phase="synthesis",
        specialist_findings=[],
    ) is (gaps == [])


@pytest.mark.unit
def test_finding_meets_minimum_generic_structured_content() -> None:
    assert finding_meets_minimum("purple", {"artifacts": ["hash-1"]}, schema_name="PurpleFinding") is True
