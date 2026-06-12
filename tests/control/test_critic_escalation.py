from __future__ import annotations

import pytest

from interfaces.control_plane.critic_service import CriticService
from interfaces.control_plane.status_store import MemoryStatusStore


@pytest.mark.unit
@pytest.mark.asyncio
async def test_critic_requires_hitl_on_low_trust(monkeypatch):
    store = MemoryStatusStore()
    critic = CriticService()
    critic.store = store
    published: list[dict] = []

    async def capture_awaiting(payload: dict) -> bool:
        published.append(payload)
        return True

    monkeypatch.setattr("interfaces.control_plane.critic_service.publish_awaiting_approval", capture_awaiting)

    feedback = await critic.handle_message(
        {
            "sender": "soc",
            "payload": {"event_id": "e1", "data": {"priority": "high", "confidence": 0.2}},
        }
    )
    assert feedback["requires_hitl"] is True
    assert len(store.awaiting_approval) == 1
    assert published


@pytest.mark.unit
@pytest.mark.asyncio
async def test_critic_hitl_blocks_auto_escalation_for_high_severity(monkeypatch):
    store = MemoryStatusStore()
    critic = CriticService()
    critic.store = store
    escalations: list[dict] = []

    async def capture_escalation(**kwargs) -> bool:
        escalations.append(kwargs)
        return True

    monkeypatch.setattr("interfaces.control_plane.critic_service.publish_escalation_event", capture_escalation)

    feedback = await critic.handle_message(
        {
            "sender": "network",
            "payload": {"event_id": "e2", "data": {"severity": "critical", "confidence": 0.95}},
        }
    )
    assert feedback.get("requires_hitl") is True
    assert not escalations


@pytest.mark.unit
@pytest.mark.asyncio
async def test_l2_approval_publishes_escalation(monkeypatch):
    store = MemoryStatusStore()
    critic = CriticService()
    critic.store = store
    escalations: list[dict] = []

    async def capture_escalation(**kwargs) -> bool:
        escalations.append(kwargs)
        return True

    monkeypatch.setattr("interfaces.control_plane.critic_service.publish_escalation_event", capture_escalation)

    approval = {
        "sender": "soc",
        "envelope": {
            "sender": "soc",
            "payload": {"event_id": "e3", "data": {"severity": "critical"}},
        },
    }
    assert await critic.escalate_after_l2_approval(approval) is True
    assert escalations[0]["source_persona"] == "soc"
    assert len(store.escalations) == 1
