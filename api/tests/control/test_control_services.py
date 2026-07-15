from __future__ import annotations

import pytest

from cys_core.application.use_cases.process_finding_critic import ProcessFindingCritic
from interfaces.control_plane.coordinator_service import CoordinatorService
from interfaces.control_plane.critic_service import CriticService
from interfaces.control_plane.status_store import MemoryStatusStore


@pytest.mark.unit
@pytest.mark.asyncio
async def test_critic_service_feedback():
    store = MemoryStatusStore()
    critic = CriticService()
    critic.store = store
    envelope = {
        "sender": "soc",
        "payload": {"event_id": "e1", "data": {"priority": "high", "confidence": 0.3}},
    }
    feedback = await critic.handle_message(envelope)
    assert feedback["trust_score"] == 0.3
    assert feedback["passed"] is False
    assert feedback["recommended_disposition"] == "revise"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_coordinator_service_narrative():
    store = MemoryStatusStore()
    coord = CoordinatorService()
    coord.store = store
    await coord.handle_message({"sender": "soc", "payload": {"event_id": "e1"}})
    assert len(store.coordinator_narratives) == 1
    narrative = store.coordinator_narratives[0]
    assert narrative["sender"] == "soc"
    assert "soc" in narrative["summary"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_low_trust_finding_fails_heuristic_gate():
    from unittest.mock import MagicMock

    critic = ProcessFindingCritic(policy_port=MagicMock(), trust_threshold=0.5)
    result = critic.execute(
        persona="soc",
        finding={"confidence": 0.2, "priority": "high"},
        investigation_id="e1",
    )
    assert result["passed"] is False
    assert result["trust_score"] == 0.2
    assert result["recommended_disposition"] == "revise"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_high_trust_finding_passes_heuristic_gate():
    from unittest.mock import MagicMock

    critic = ProcessFindingCritic(policy_port=MagicMock(), trust_threshold=0.5)
    result = critic.execute(
        persona="network",
        finding={"severity": "critical", "confidence": 0.95},
        investigation_id="e2",
    )
    assert result["passed"] is True
    assert result["trust_score"] == 0.95
