from __future__ import annotations

import pytest

from cys_core.application.use_cases.process_finding_critic import ProcessFindingCritic
from interfaces.control_plane.critic_service import CriticService
from interfaces.control_plane.status_store import MemoryStatusStore


@pytest.mark.unit
@pytest.mark.asyncio
async def test_critic_requires_revision_on_low_trust():
    store = MemoryStatusStore()
    critic = CriticService()
    critic.store = store

    feedback = await critic.handle_message(
        {
            "sender": "soc",
            "payload": {"event_id": "e1", "data": {"priority": "high", "confidence": 0.2}},
        }
    )
    assert feedback["passed"] is False
    assert feedback["trust_score"] == 0.2
    assert feedback["recommended_disposition"] == "revise"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_critic_high_severity_still_runs_heuristic_gate():
    from unittest.mock import MagicMock

    critic = ProcessFindingCritic(policy_port=MagicMock(), trust_threshold=0.5)
    feedback = critic.execute(
        persona="network",
        finding={"severity": "critical", "confidence": 0.95},
        investigation_id="e2",
    )
    assert feedback["passed"] is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_critic_revision_enqueued_when_finding_fails():
    store = MemoryStatusStore()
    critic = CriticService()
    critic.store = store

    feedback = await critic.handle_message(
        {
            "sender": "soc",
            "payload": {
                "event_id": "e3",
                "correlation_id": "e3",
                "data": {"priority": "high", "confidence": 0.1, "summary": "bad"},
            },
        }
    )
    assert feedback["passed"] is False
    assert feedback.get("revision_enqueued") is True
