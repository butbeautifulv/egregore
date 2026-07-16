from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from interfaces.control_plane.critic_service import CriticService


@pytest.mark.integration
@pytest.mark.asyncio
async def test_critic_flags_low_trust_finding(monkeypatch):
    egress = MagicMock()
    monkeypatch.setattr(
        "interfaces.control_plane.critic_service.get_container",
        lambda: MagicMock(
            get_engagement_egress=lambda: egress,
            get_profile_policy_port=lambda: MagicMock(get_trust_floor=lambda _pid: 0.5),
        ),
    )
    monkeypatch.setattr(
        "cys_core.application.use_cases.process_finding_critic.record_critic_verdict",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "interfaces.control_plane.critic_service.build_agent_bus",
        lambda *a, **k: MagicMock(send_message=lambda *a, **k: {"signature": "s"}),
    )
    guard = MagicMock()
    guard.revision_cap_exceeded.return_value = False
    monkeypatch.setattr(
        "interfaces.control_plane.critic_service.get_engagement_bus_guard",
        lambda: guard,
    )
    critic = CriticService()

    result = await critic.handle_message(
        {
            "sender": "soc",
            "payload": {
                "event_id": "e1",
                "correlation_id": "e1",
                "data": {"severity": "critical", "confidence": 0.2, "trust_score": 0.2},
            },
        }
    )
    assert result.get("passed") is False
    egress.publish_event.assert_called_once()
