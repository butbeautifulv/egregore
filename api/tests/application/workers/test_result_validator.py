from __future__ import annotations

import pytest

from cys_core.application.workers.result_validator import WorkerResultValidator
from cys_core.domain.findings.models import ConsultantFinding, SocFinding
from cys_core.domain.security.exceptions import SecurityViolation
from cys_core.domain.security.guardrails import OutputGuardrails


class _SchemaRegistry:
    def get(self, name: str):
        if name == "SocFinding":
            return SocFinding
        if name == "ConsultantFinding":
            return ConsultantFinding
        return None


@pytest.mark.unit
def test_result_validator_attaches_sgr_metadata():
    validator = WorkerResultValidator(schema_registry=_SchemaRegistry(), guardrails=OutputGuardrails())
    result = validator.validate(
        result={
            "reasoning_steps": ["a"],
            "plan_status": "ok",
            "incident_id": "i1",
            "priority": "high",
            "confidence": 0.8,
            "summary": "s",
        },
        schema_name="SocFinding",
    )
    assert result["sgr_metadata"]["reasoning_steps"] == ["a"]


@pytest.mark.unit
def test_result_validator_preserves_consultant_plain_text():
    validator = WorkerResultValidator(schema_registry=_SchemaRegistry(), guardrails=OutputGuardrails())
    text = "Я консультант: объясняю методологию CYS и best practices."
    result = validator.validate(result={"raw_response": text}, schema_name="ConsultantFinding")
    assert result.get("raw_response") == text
    validator = WorkerResultValidator(
        schema_registry=_SchemaRegistry(),
        guardrails=OutputGuardrails(),
        dev_schema_bypass=False,
    )
    with pytest.raises(SecurityViolation):
        validator.validate(result={"confidence": 2.0}, schema_name="SocFinding")
