from typing import cast

import pytest
from pydantic import ValidationError

from cys_core.domain.findings.models import CriticResult, FindingEnvelope, RedTeamFinding, WorkerAgentName


@pytest.mark.unit
def test_red_team_finding_confidence_bounds():
    assert RedTeamFinding(confidence=0.5).confidence == 0.5
    with pytest.raises(ValidationError):
        RedTeamFinding(confidence=1.5)


@pytest.mark.unit
def test_critic_result_defaults():
    result = CriticResult()
    assert result.trust_score == 0.0
    assert result.issues_detected == []


@pytest.mark.unit
def test_finding_envelope_agent_literal():
    env = FindingEnvelope(agent="redteam", data={"severity": "low"})
    assert env.agent == "redteam"
    env_intel = FindingEnvelope(agent="intel", data={"summary": "test"})
    assert env_intel.agent == "intel"
    env_purple = FindingEnvelope(agent="purple", data={"summary": "coverage"})
    assert env_purple.agent == "purple"
    with pytest.raises(ValidationError):
        FindingEnvelope(agent=cast(WorkerAgentName, "unknown"), data={})


@pytest.mark.unit
def test_kill_chain_overlay_fields():
    finding = RedTeamFinding(
        attack_phase="exploitation",
        mitre_tactics=["TA0001"],
        mitre_techniques=["T1190"],
    )
    assert finding.attack_phase == "exploitation"
    assert finding.mitre_techniques == ["T1190"]
