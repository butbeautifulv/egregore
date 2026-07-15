from __future__ import annotations

import pytest

from cys_core.application.use_cases.process_finding_critic import ProcessFindingCritic
from tests.application.port_fakes import fake_policy_port


@pytest.mark.unit
def test_critic_passes_high_trust_score(monkeypatch):
    monkeypatch.setattr(
        "cys_core.application.use_cases.process_finding_critic.record_critic_verdict",
        lambda *a, **k: None,
    )
    critic = ProcessFindingCritic(policy_port=fake_policy_port(), trust_threshold=0.5)
    out = critic.execute(persona="soc", finding={"trust_score": 0.9})
    assert out["passed"] is True
    assert out["trust_score"] == 0.9


@pytest.mark.unit
def test_critic_fails_low_trust_score(monkeypatch):
    monkeypatch.setattr(
        "cys_core.application.use_cases.process_finding_critic.record_critic_verdict",
        lambda *a, **k: None,
    )
    critic = ProcessFindingCritic(policy_port=fake_policy_port(), trust_threshold=0.5)
    out = critic.execute(persona="soc", finding={"trust_score": 0.2})
    assert out["passed"] is False
