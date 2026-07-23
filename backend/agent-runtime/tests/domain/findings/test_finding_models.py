import pytest
from pydantic import ValidationError

from cys_core.domain.findings.models import CriticResult, FindingEnvelope
from cys_core.domain.findings.packs.cybersec_soc import RedTeamFinding


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
def test_finding_envelope_agent_is_plain_str():
    # WorkerAgentName is a plain str (MSP_BACKLOG.md §8.4 point 1), not a closed
    # Literal — persona names are catalog/profile-pack data, not something
    # cys_core/domain hardcodes. Any persona name string is accepted here;
    # FindingEnvelope has no live caller in src/ to enforce catalog membership.
    env = FindingEnvelope(agent="redteam", data={"severity": "low"})
    assert env.agent == "redteam"
    env_intel = FindingEnvelope(agent="intel", data={"summary": "test"})
    assert env_intel.agent == "intel"
    env_purple = FindingEnvelope(agent="purple", data={"summary": "coverage"})
    assert env_purple.agent == "purple"
    env_other = FindingEnvelope(agent="a-toy-pack-persona", data={})
    assert env_other.agent == "a-toy-pack-persona"


@pytest.mark.unit
def test_kill_chain_overlay_fields():
    finding = RedTeamFinding(
        attack_phase="exploitation",
        mitre_tactics=["TA0001"],
        mitre_techniques=["T1190"],
    )
    assert finding.attack_phase == "exploitation"
    assert finding.mitre_techniques == ["T1190"]
