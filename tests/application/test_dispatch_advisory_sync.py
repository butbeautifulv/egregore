from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cys_core.application.use_cases.dispatch_event import use_async_investigation_planner
from cys_core.domain.events.models import SecurityEvent


@pytest.mark.unit
def test_advisory_investigation_uses_sync_planner(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MANUAL_INVESTIGATION_ASYNC", "true")
    from bootstrap.settings import get_settings

    get_settings.cache_clear()
    from cys_core.application.runtime_config import configure_from_settings

    configure_from_settings(get_settings())

    event = SecurityEvent(
        id="evt-ad",
        type="manual.investigation",
        severity="low",
        source="test",
        payload={"goal": "Как защитить Active Directory?"},
    )
    assert use_async_investigation_planner(event, event.payload) is False


@pytest.mark.unit
def test_incident_investigation_stays_async(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MANUAL_INVESTIGATION_ASYNC", "true")
    from bootstrap.settings import get_settings

    get_settings.cache_clear()
    from cys_core.application.runtime_config import configure_from_settings

    configure_from_settings(get_settings())

    event = SecurityEvent(
        id="evt-inc",
        type="manual.investigation",
        severity="high",
        source="test",
        payload={"goal": "Investigate lateral movement on DC-01"},
    )
    assert use_async_investigation_planner(event, event.payload) is True
