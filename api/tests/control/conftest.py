from __future__ import annotations

import pytest

from cys_core.application.bus_guard_config import BusGuardConfig
from cys_core.application.engagement_bus_guard import (
    EngagementBusGuard,
    configure_engagement_bus_guard,
    reset_engagement_bus_guard,
)


@pytest.fixture(autouse=True)
def _engagement_bus_guard() -> None:
    reset_engagement_bus_guard()
    configure_engagement_bus_guard(
        EngagementBusGuard(
            config=BusGuardConfig(
                max_total_jobs_window=50,
                dedup_trip_threshold=5,
                pingpong_trip_threshold=3,
                noop_churn_threshold=10,
                guard_window_seconds=600,
                redis_url="redis://localhost:6379/0",
            )
        )
    )
    yield
    reset_engagement_bus_guard()


@pytest.fixture(autouse=True)
def _mock_agent_bus(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Bus:
        def send_message(self, sender: str, recipient: str, msg_type: str, payload: dict) -> dict:
            return {
                "sender": sender,
                "recipient": recipient,
                "message_type": msg_type,
                "payload": payload,
                "signature": "test-sig",
            }

    monkeypatch.setattr(
        "interfaces.control_plane.critic_service.build_agent_bus",
        lambda *args, **kwargs: _Bus(),
    )
