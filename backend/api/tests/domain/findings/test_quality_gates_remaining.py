from __future__ import annotations

import pytest

from cys_core.domain.evidence.models import EvidenceManifest
from cys_core.domain.findings.quality_gates import (
    coerce_consultant_advisory_result,
    consultant_finding_gaps,
    finding_meets_minimum,
)
from cys_core.domain.parsing.json_text import parse_json_text, parse_loose_structured_text


@pytest.mark.unit
def test_coerce_consultant_advisory_result_noop_when_complete() -> None:
    complete = {
        "topic": "Advisory",
        "summary": "Use MFA",
        "recommendations": ["Enable MFA", "Review access"],
        "confidence": 0.8,
    }
    assert coerce_consultant_advisory_result(complete, goal="Advisory") is False


@pytest.mark.unit
def test_coerce_consultant_advisory_result_no_text() -> None:
    result: dict[str, object] = {"raw": "   "}
    assert coerce_consultant_advisory_result(result, goal="Advisory") is False


@pytest.mark.unit
def test_consultant_finding_gaps_invalid_confidence() -> None:
    gaps = consultant_finding_gaps(
        {
            "topic": "Advisory",
            "summary": "text",
            "recommendations": ["a", "b"],
            "confidence": "bad",
        }
    )
    assert "missing_confidence" in gaps


@pytest.mark.unit
def test_finding_meets_minimum_soc_missing_summary() -> None:
    assert finding_meets_minimum("soc", {}, schema_name="SocFinding") is False


@pytest.mark.unit
def test_finding_meets_minimum_consultant_incomplete() -> None:
    assert finding_meets_minimum("consultant", {"summary": "only one"}, schema_name="ConsultantFinding") is False


@pytest.mark.unit
def test_finding_meets_minimum_soc_without_manifest() -> None:
    assert finding_meets_minimum("soc", {"summary": "ok"}, schema_name="SocFinding", manifest=None) is True


@pytest.mark.unit
def test_finding_meets_minimum_consultant_synthesis_phase() -> None:
    manifest = EvidenceManifest(telemetry_level="rich", max_confidence=1.0)
    result = {
        "topic": "Wrap",
        "summary": "No new entities.",
        "recommendations": ["A", "B"],
        "confidence": 0.8,
    }
    assert (
        finding_meets_minimum(
            "consultant",
            result,
            schema_name="ConsultantFinding",
            upstream_manifests={"soc": manifest},
            phase="synthesis",
            specialist_findings=[],
        )
        is True
    )


@pytest.mark.unit
def test_parse_json_text_literal_eval_failures() -> None:
    assert parse_json_text("```json\n{\"a\": 1}\n```") == {"a": 1}
    assert parse_loose_structured_text("personas=[bad") is None
    assert parse_loose_structured_text("Returning structured response: personas=['soc']") is not None
    assert parse_loose_structured_text(
        "prefix personas=['soc'] sub_goals={'soc': 'x'} rationale='why' execution_mode=None synthesis_persona=None"
    ) is not None
