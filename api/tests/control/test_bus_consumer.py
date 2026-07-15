from __future__ import annotations

import pytest

from interfaces.control_plane.bus_consumer import BusFindingsConsumer


@pytest.mark.unit
@pytest.mark.asyncio
async def test_bus_consumer_dispatches_matching_channel():
    handled: list[dict] = []

    async def handler(envelope: dict) -> None:
        handled.append(envelope)

    async def fake_consume(*, timeout: float, group_id: str):
        return {"channel": "critic", "sender": "soc", "payload": {"event_id": "e1"}}

    consumer = BusFindingsConsumer("critic", handler, consume=fake_consume)
    assert await consumer.process_one() is True
    assert handled[0]["sender"] == "soc"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_bus_consumer_skips_other_channel():
    handled: list[dict] = []

    async def handler(envelope: dict) -> None:
        handled.append(envelope)

    async def fake_consume(*, timeout: float, group_id: str):
        return {"channel": "coordinator", "sender": "soc"}

    consumer = BusFindingsConsumer("critic", handler, consume=fake_consume)
    assert await consumer.process_one() is False
    assert handled == []
