from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_aingest_kafka_publishes_raw_event(monkeypatch):
    """When USE_KAFKA=true, aingest publishes to security.events.raw."""
    from config import Settings
    from ingress.router import EventIngress, _publish_raw_event  # noqa: F401

    monkeypatch.setenv("USE_KAFKA", "true")
    s = Settings(_env_file=None)
    monkeypatch.setattr("ingress.router.settings", s)

    published = []

    async def fake_publish(event, bootstrap_servers):
        published.append(event)

    monkeypatch.setattr("ingress.router._publish_raw_event", fake_publish)

    ingress = EventIngress()
    event, decision, job_ids = await ingress.aingest(
        "siem.alert", {"alert": "test"}, severity="high"
    )

    assert len(published) == 1
    assert published[0].id == event.id
    assert job_ids == []
    assert decision.event_id == event.id
