from __future__ import annotations

import pytest

from cys_core.application.workers.result_validator import WorkerResultValidator
from cys_core.domain.findings.models import SocFinding
from cys_core.domain.security.guardrails import OutputGuardrails
from cys_core.domain.security.exceptions import SecurityViolation


class _SchemaRegistry:
    def get(self, name: str):
        if name == "SocFinding":
            return SocFinding
        return None


@pytest.mark.unit
def test_result_validator_attaches_sgr_metadata():
    validator = WorkerResultValidator(schema_registry=_SchemaRegistry(), guardrails=OutputGuardrails())
    result = validator.validate(
        result={"reasoning_steps": ["a"], "plan_status": "ok", "incident_id": "i1", "priority": "high", "confidence": 0.8, "summary": "s"},
        schema_name="SocFinding",
    )
    assert result["sgr_metadata"]["reasoning_steps"] == ["a"]


@pytest.mark.unit
def test_result_validator_raises_on_schema_mismatch():
    validator = WorkerResultValidator(
        schema_registry=_SchemaRegistry(),
        guardrails=OutputGuardrails(),
        dev_schema_bypass=False,
    )
    with pytest.raises(SecurityViolation):
        validator.validate(result={"confidence": 2.0}, schema_name="SocFinding")
