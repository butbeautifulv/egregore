from __future__ import annotations

import pytest
from pydantic import ValidationError

from cys_core.domain.findings.models import ConductorStepResult
from cys_core.domain.findings.packs.cybersec_soc import SocFinding


@pytest.mark.unit
def test_soc_finding_coerces_string_evidence_and_gaps() -> None:
    finding = SocFinding.model_validate(
        {
            "summary": "Suspicious login",
            "evidence": ["obs:evt:1:host:workstation"],
            "data_gaps": ["subject.process.cmdline"],
        }
    )
    assert finding.evidence[0].obs_id == "obs:evt:1:host:workstation"
    assert finding.data_gaps[0].field == "subject.process.cmdline"


@pytest.mark.unit
def test_soc_finding_coerces_non_list_evidence_and_gaps() -> None:
    finding = SocFinding.model_validate({"summary": "ok", "evidence": "ignored", "data_gaps": 123})
    assert finding.evidence == []
    assert finding.data_gaps == []


@pytest.mark.unit
def test_soc_finding_rejects_invalid_dict_entries() -> None:
    with pytest.raises(ValidationError):
        SocFinding.model_validate(
            {
                "summary": "Suspicious login",
                "evidence": [{"obs_id": "obs:1", "excerpt": "x"}, {"ignored": True}],
            }
        )


@pytest.mark.unit
def test_conductor_step_result_coerces_reasoning_lists() -> None:
    result = ConductorStepResult.model_validate(
        {"reasoning_steps": 1, "remaining_steps": "next", "reply": "ok"}
    )
    assert result.reasoning_steps == ["1"]
    assert result.remaining_steps == ["next"]


@pytest.mark.unit
def test_conductor_step_result_coerces_unknown_step_list_type() -> None:
    result = ConductorStepResult.model_validate({"reasoning_steps": {"bad": 1}, "reply": "ok"})
    assert result.reasoning_steps == []
    result = ConductorStepResult.model_validate(
        {"reasoning_steps": [1, 2], "remaining_steps": 0, "reply": "ok"}
    )
    assert result.reasoning_steps == ["1", "2"]
    assert result.remaining_steps == []
