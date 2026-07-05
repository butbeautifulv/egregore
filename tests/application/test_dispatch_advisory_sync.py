from __future__ import annotations

import pytest

from cys_core.application.use_cases.engagement_planner import use_async_engagement_planner
from cys_core.domain.events.models import SecurityEvent


@pytest.mark.unit
def test_advisory_investigation_uses_async_planner_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENGAGEMENT_ASYNC_PLANNING", "true")
    from bootstrap.settings import get_settings

    get_settings.cache_clear()
    from cys_core.application.runtime_config import configure_from_settings

    configure_from_settings(get_settings())

    event = SecurityEvent(
        id="evt-ad",
        type="engagement.start",
        severity="low",
        source="test",
        payload={"goal": "Как защитить Active Directory?", "plan_strategy": "meta_llm"},
    )
    assert use_async_engagement_planner(event, event.payload) is True


@pytest.mark.unit
def test_incident_investigation_stays_async(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENGAGEMENT_ASYNC_PLANNING", "true")
    from bootstrap.settings import get_settings

    get_settings.cache_clear()
    from cys_core.application.runtime_config import configure_from_settings

    configure_from_settings(get_settings())

    event = SecurityEvent(
        id="evt-inc",
        type="engagement.start",
        severity="high",
        source="test",
        payload={"goal": "Investigate lateral movement on DC-01", "plan_strategy": "meta_llm"},
    )
    assert use_async_engagement_planner(event, event.payload) is True
