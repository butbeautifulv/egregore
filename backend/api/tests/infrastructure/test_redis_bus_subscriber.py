from __future__ import annotations

import json

import pytest

from cys_core.infrastructure.bus_transport import RedisBusTransport


class _FakePubSub:
    def __init__(self, messages: list[dict]) -> None:
        self._messages = list(messages)

    def subscribe(self, channel: str) -> None:
        return

    def get_message(self, timeout: float = 1.0):
        if not self._messages:
            return None
        return self._messages.pop(0)

    def close(self) -> None:
        return


class _FakeRedis:
    def __init__(self) -> None:
        self.published: list[tuple[str, str]] = []

    def ping(self) -> bool:
        return True

    def publish(self, channel: str, payload: str) -> None:
        self.published.append((channel, payload))

    def pubsub(self, ignore_subscribe_messages: bool = True) -> _FakePubSub:
        return _FakePubSub(
            [
                {
                    "type": "message",
                    "channel": "cys:bus:critic",
                    "data": json.dumps({"recipient": "critic", "payload": {"ok": True}}),
                }
            ]
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_redis_bus_subscriber_dispatches_handler(monkeypatch):
    transport = RedisBusTransport(redis_url="redis://fake")
    transport._redis = _FakeRedis()
    seen: list[dict] = []

    async def handler(message: dict) -> None:
        seen.append(message)

    transport.subscribe("critic", handler)
    transport.start_subscriber_loop(["critic"])
    import time

    time.sleep(0.2)
    assert seen and seen[0]["recipient"] == "critic"
