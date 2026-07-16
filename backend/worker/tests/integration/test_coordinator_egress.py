from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from interfaces.control_plane.coordinator_service import CoordinatorService


@pytest.mark.integration
@pytest.mark.asyncio
async def test_coordinator_publishes_report_with_job_id(monkeypatch) -> None:
    egress = MagicMock()
    monkeypatch.setattr(
        "interfaces.control_plane.coordinator_service.get_status_store",
        lambda: MagicMock(record_narrative=MagicMock()),
    )
    monkeypatch.setattr(
        "interfaces.control_plane.coordinator_service.get_control_narrator",
        lambda: MagicMock(
            narrate=AsyncMock(return_value="Агент consultant завершил работу.")
        ),
    )
    monkeypatch.setattr(
        "interfaces.control_plane.coordinator_service.get_container",
        lambda: MagicMock(get_engagement_egress=lambda: egress),
    )
    monkeypatch.setattr(
        "interfaces.control_plane.coordinator_service.publish_assistant_snapshot",
        lambda **_kwargs: None,
    )

    coordinator = CoordinatorService()
    await coordinator.handle_message(
        {
            "sender": "consultant",
            "payload": {
                "event_id": "evt-1",
                "correlation_id": "eng-1",
                "tenant_id": "default",
                "data": {"summary": "Deploy EDR", "topic": "Malware"},
            },
        }
    )

    egress.publish_event.assert_called_once()
    args = egress.publish_event.call_args[0]
    assert args[0] == "eng-1"
    assert args[1] == "report"
    assert args[2]["job_id"] == "consultant:eng-1"
    assert "summary" in args[2]
