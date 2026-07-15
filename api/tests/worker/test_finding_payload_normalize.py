from __future__ import annotations

import pytest

from cys_core.application.workers.finding_quality import finding_meets_minimum, normalize_finding_payload
from cys_core.application.workers.result_validator import WorkerResultValidator
from cys_core.domain.security.guardrails import OutputGuardrails
from cys_core.registry.schemas import schema_registry


@pytest.mark.unit
def test_normalize_finding_payload_unwraps_finding_dict() -> None:
    wrapped = {
        "finding": {
            "summary": "IOC analysis complete",
            "iocs": ["10.0.0.1"],
            "confidence": 0.5,
        }
    }
    out = normalize_finding_payload(wrapped)
    assert out["summary"] == "IOC analysis complete"
    assert out["iocs"] == ["10.0.0.1"]


@pytest.mark.unit
def test_normalize_finding_payload_preserves_redteam_string_finding() -> None:
    data = {"finding": "Credential spray observed", "severity": "high"}
    out = normalize_finding_payload(data)
    assert out["finding"] == "Credential spray observed"
    assert out["severity"] == "high"


@pytest.mark.unit
def test_wrapped_intel_finding_passes_minimum_gate() -> None:
    wrapped = {
        "finding": {
            "summary": "No external threat matches",
            "iocs": ["10.96.183.220"],
            "confidence": 0.2,
        }
    }
    assert finding_meets_minimum("intel", wrapped, schema_name="IntelFinding") is True


@pytest.mark.unit
def test_result_validator_unwraps_before_schema_validation() -> None:
    validator = WorkerResultValidator(
        schema_registry=schema_registry,
        guardrails=OutputGuardrails(),
    )
    wrapped = {
        "finding": {
            "summary": "Intel summary",
            "iocs": ["host.example.com"],
            "confidence": 0.3,
        }
    }
    out = validator.validate(result=wrapped, schema_name="IntelFinding")
    assert out["summary"] == "Intel summary"
    assert out["iocs"] == ["host.example.com"]
