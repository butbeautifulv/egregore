from __future__ import annotations

import pytest

from cys_core.application.adapters.security_event_adapter import security_event_to_domain
from cys_core.domain.events.domain_events import TaskEvent
from cys_core.domain.events.models import SecurityEvent


@pytest.mark.unit
def test_security_event_to_domain_task_event() -> None:
    event = SecurityEvent(
        id="evt-1",
        type="manual.consultation",
        severity="high",
        payload={"goal": "triage", "profile_id": "cybersec-soc"},
        correlation_id="inv-1",
    )
    domain = security_event_to_domain(event, domain="cybersecurity")
    assert isinstance(domain, TaskEvent)
    assert domain.domain == "cybersecurity"
    assert domain.task_kind == "consultation"
    assert domain.profile_id == "cybersec-soc"
