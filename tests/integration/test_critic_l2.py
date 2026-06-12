from __future__ import annotations

import pytest

from interfaces.control_plane.critic_service import CriticService
from interfaces.control_plane.status_store import MemoryStatusStore


@pytest.mark.integration
@pytest.mark.asyncio
async def test_critic_l2_then_escalation(monkeypatch):
    store = MemoryStatusStore()
    critic = CriticService()
    critic.store = store

    async def noop_awaiting(_payload: dict) -> bool:
        return True

    async def capture_escalation(**_kwargs) -> bool:
        return True

    monkeypatch.setattr("interfaces.control_plane.critic_service.publish_awaiting_approval", noop_awaiting)
    monkeypatch.setattr("interfaces.control_plane.critic_service.publish_escalation_event", capture_escalation)

    feedback = await critic.handle_message(
        {
            "sender": "soc",
            "payload": {"event_id": "e1", "data": {"severity": "critical", "confidence": 0.2}},
        }
    )
    assert feedback.get("requires_hitl") is True

    approval = {
        "envelope": {
            "sender": "soc",
            "payload": {"event_id": "e1", "data": {"severity": "critical"}},
        }
    }
    assert await critic.escalate_after_l2_approval(approval) is True
    assert len(store.escalations) == 1
