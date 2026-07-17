from __future__ import annotations

import pytest

from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID
from cys_core.domain.events.domain_events import DomainEvent, TaskEvent


@pytest.mark.unit
def test_domain_event_defaults() -> None:
    event = DomainEvent(id="evt-1", domain="soc", event_type="siem.alert")
    assert event.tenant_id == "default"
    assert event.profile_id == DEFAULT_PROFILE_ID
    assert event.severity == "medium"
    assert event.payload == {}


@pytest.mark.unit
def test_task_event_task_kind() -> None:
    event = TaskEvent(
        id="evt-2",
        domain="consultant",
        event_type="task.created",
        task_kind="investigation",
        severity="high",
    )
    assert event.task_kind == "investigation"
    assert event.severity == "high"
