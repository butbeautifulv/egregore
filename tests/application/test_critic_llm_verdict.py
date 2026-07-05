from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from cys_core.application.use_cases.process_finding_critic import ProcessFindingCritic
from tests.application.port_fakes import fake_policy_port


@pytest.mark.unit
def test_critic_passes_high_trust_score(monkeypatch):
    monkeypatch.setattr("cys_core.application.use_cases.process_finding_critic.record_critic_verdict", lambda *a, **k: None)
    critic = ProcessFindingCritic(policy_port=fake_policy_port(), trust_threshold=0.5)
    out = critic.execute(persona="soc", finding={"trust_score": 0.9})
    assert out["passed"] is True
    assert out["trust_score"] == 0.9


@pytest.mark.unit
def test_critic_fails_low_trust_score(monkeypatch):
    monkeypatch.setattr("cys_core.application.use_cases.process_finding_critic.record_critic_verdict", lambda *a, **k: None)
    critic = ProcessFindingCritic(policy_port=fake_policy_port(), trust_threshold=0.5)
    out = critic.execute(persona="soc", finding={"trust_score": 0.2})
    assert out["passed"] is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_critic_llm_verdict_uses_runtime(monkeypatch):
    monkeypatch.setattr("cys_core.application.use_cases.process_finding_critic.record_critic_verdict", lambda *a, **k: None)
    runtime = MagicMock()
    runtime.arun = AsyncMock(
        return_value={
            "trust_score": 0.9,
            "issues_detected": [],
            "validated_claims": ["summary ok"],
            "reasoning_notes": ["evidence sufficient"],
            "recommended_disposition": "accept",
        }
    )
    critic = ProcessFindingCritic(
        policy_port=fake_policy_port(),
        trust_threshold=0.5,
        runtime=runtime,
        use_llm_judge=True,
    )
    out = await critic.execute_async(
        persona="consultant",
        finding={"summary": "test"},
        investigation_id="eng-1",
        tenant_id="default",
    )
    assert out["passed"] is True
    assert out["issues_detected"] == []
    runtime.arun.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_critic_llm_disabled_uses_trust_gate(monkeypatch):
    monkeypatch.setattr("cys_core.application.use_cases.process_finding_critic.record_critic_verdict", lambda *a, **k: None)
    runtime = MagicMock()
    runtime.arun = AsyncMock()
    critic = ProcessFindingCritic(
        policy_port=fake_policy_port(),
        trust_threshold=0.5,
        runtime=runtime,
        use_llm_judge=False,
    )
    out = await critic.execute_async(
        persona="consultant",
        finding={"trust_score": 0.8},
        investigation_id="eng-1",
    )
    assert out["passed"] is True
    runtime.arun.assert_not_called()
