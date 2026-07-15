from __future__ import annotations

import pytest

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
    assert "low_trust_score" in feedback["issues_detected"]
    assert feedback.get("requires_hitl") is True
    assert len(store.critic_feedback) == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_coordinator_service_narrative():
    store = MemoryStatusStore()
    coord = CoordinatorService()
    coord.store = store
    await coord.handle_message({"sender": "soc", "payload": {"event_id": "e1"}})
    assert len(store.coordinator_narratives) == 1
    assert "soc" in store.coordinator_narratives[0]
