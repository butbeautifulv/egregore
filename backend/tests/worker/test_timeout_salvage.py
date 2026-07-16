from __future__ import annotations

import pytest

from cys_core.application.workers.finding_quality import finding_meets_minimum
from cys_core.application.workers.timeout_salvage import build_salvage_finding
from cys_core.application.workers.tool_execution_tracker import (
    clear_tool_execution_count,
    get_tool_outputs,
    get_veil_tool_count,
    record_evidence_manifest,
    record_tool_output,
    record_veil_tool,
)
from cys_core.domain.evidence.models import DataGap, EvidenceManifest, Observation


@pytest.mark.unit
def test_record_tool_output_and_veil_count() -> None:
    clear_tool_execution_count("job-out")
    record_tool_output("job-out", "investigate_incident", '{"summary":"incident context"}')
    record_veil_tool("job-out")
    record_veil_tool("job-out")
    assert len(get_tool_outputs("job-out")) == 1
    assert get_veil_tool_count("job-out") == 2
    clear_tool_execution_count("job-out")
    assert get_veil_tool_count("job-out") == 0


@pytest.mark.unit
def test_build_salvage_finding_soc_from_investigate_incident() -> None:
    outputs = [
        (
            "investigate_incident",
            '{"success": true, "incident": {"name": "Malware on host", "severity": "high"}}',
        )
    ]
    finding = build_salvage_finding("soc", outputs)
    assert finding is not None
    assert finding["incomplete"] is True
    assert finding["salvage_reason"] == "worker_job_timeout"
    assert "Malware" in finding["summary"]


@pytest.mark.unit
def test_build_salvage_finding_intel_from_enrich_ioc() -> None:
    outputs = [
        ("enrich_ioc", "IOC 192.168.1.50 marked malicious in TI feed"),
    ]
    finding = build_salvage_finding("intel", outputs)
    assert finding is not None
    assert finding.get("summary")
    assert "192.168.1.50" in finding.get("iocs", [])


@pytest.mark.unit
def test_build_salvage_finding_returns_none_without_outputs() -> None:
    assert build_salvage_finding("soc", []) is None


@pytest.mark.unit
def test_build_salvage_finding_soc_manifest_grounded_recursion() -> None:
    job_id = "job-salvage-manifest"
    clear_tool_execution_count(job_id)
    manifest = EvidenceManifest(
        telemetry_level="sparse",
        max_confidence=0.5,
        observations=[
            Observation(
                obs_id="obs:host:ms-113",
                kind="host",
                value="ms-113.tpsgroup.ru",
                source_tool="investigate_incident",
                source_path="incident.targets",
            ),
        ],
        data_gaps=[
            DataGap(field="subject.process.cmdline", reason="not_in_siem"),
        ],
    )
    record_evidence_manifest(job_id, "investigate_incident", manifest)
    outputs = [
        (
            "investigate_incident",
            '{"incident": {"key": "INC-893776", "category": "Failed_Access"}}',
        )
    ]
    finding = build_salvage_finding(
        "soc",
        outputs,
        job_id=job_id,
        salvage_reason="recursion_limit_exhausted",
    )
    assert finding is not None
    assert finding["salvage_reason"] == "recursion_limit_exhausted"
    assert finding["telemetry_level"] == "sparse"
    assert finding["evidence"]
    assert finding["data_gaps"]
    clear_tool_execution_count(job_id)


@pytest.mark.unit
def test_build_salvage_finding_skips_ladder_block_messages() -> None:
    outputs = [
        ("investigate_incident", "investigate_incident already completed. Emit SocFinding JSON"),
        (
            "investigate_incident",
            '{"incident": {"key": "INC-893812", "description": "Port scan from 10.248.74.216"}}',
        ),
    ]
    finding = build_salvage_finding("soc", outputs)
    assert finding is not None
    assert "Port scan" in finding["summary"]
    assert "already completed" not in finding["summary"]


@pytest.mark.unit
def test_build_salvage_finding_consultant_recursion() -> None:
    outputs = [
        ("playbook_search", '{"count":2,"skills":[{"name":"malware-defense"}]}'),
        ("load_skill", "Loaded veil-knowledge skill with deployment guidance."),
    ]
    finding = build_salvage_finding(
        "consultant",
        outputs,
        salvage_reason="recursion_limit_exhausted",
        goal="Как защититься от вирусов?",
    )
    assert finding is not None
    assert finding["topic"] == "Как защититься от вирусов?"
    assert finding["summary"]
    assert len(finding["recommendations"]) >= 2
    assert finding_meets_minimum(
        "consultant",
        finding,
        schema_name="ConsultantFinding",
    )
