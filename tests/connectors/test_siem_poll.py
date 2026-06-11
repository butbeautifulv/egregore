from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from connectors.siem_poll.client import MockSiemBackend, SiemPollClient
from connectors.siem_poll.models import RawSiemEvent


@pytest.mark.asyncio
async def test_mock_backend_fetch_all():
    backend = MockSiemBackend()
    backend.seed_default_events()
    events = await backend.fetch_events()
    assert len(events) == 5


@pytest.mark.asyncio
async def test_mock_backend_fetch_since():
    backend = MockSiemBackend()
    backend.seed_default_events()
    events = await backend.fetch_events()
    first_id = events[0].raw_id
    since_events = await backend.fetch_events(since_id=first_id)
    assert len(since_events) == 4


@pytest.mark.asyncio
async def test_mock_backend_add_event():
    backend = MockSiemBackend()
    raw = backend.add_event(event_type="edr.alert", host="test-host", severity="high")
    assert raw.event_type == "edr.alert"
    assert raw.host == "test-host"
    fetched = await backend.fetch_events()
    assert len(fetched) == 1


@pytest.mark.asyncio
async def test_poll_client_sends_events():
    backend = MockSiemBackend()
    backend.seed_default_events()

    client = SiemPollClient(backend=backend, ingress_url="http://test", max_events=5)

    async def fake_post_event(http_client, raw):
        client._last_id = raw.raw_id
        client._events_sent += 1
        return True

    mock_http = MagicMock()

    with patch.object(client, "_post_event", side_effect=fake_post_event):
        count = await client.poll_once(mock_http)

    assert count == 5
    assert client._events_sent == 5


@pytest.mark.asyncio
async def test_poll_client_stops_at_max_events():
    backend = MockSiemBackend()
    backend.seed_default_events()

    client = SiemPollClient(backend=backend, ingress_url="http://test", max_events=3)

    async def fake_post_event(http_client, raw):
        client._last_id = raw.raw_id
        client._events_sent += 1
        return True

    mock_http = MagicMock()

    with patch.object(client, "_post_event", side_effect=fake_post_event):
        await client.poll_once(mock_http)

    assert client._events_sent == 3
    assert client._stop_event.is_set()


@pytest.mark.asyncio
async def test_post_event_success():
    backend = MockSiemBackend()
    backend.add_event(event_type="alert", severity="high", host="host-01", message="test")
    raw = (await backend.fetch_events())[0]

    client = SiemPollClient(backend=backend, ingress_url="http://test")

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    mock_http_client = AsyncMock()
    mock_http_client.post = AsyncMock(return_value=mock_response)

    result = await client._post_event(mock_http_client, raw)
    assert result is True
    assert client._events_sent == 1
    assert client._last_id == raw.raw_id


@pytest.mark.asyncio
async def test_post_event_failure_returns_false():
    backend = MockSiemBackend()
    backend.add_event()
    raw = (await backend.fetch_events())[0]

    client = SiemPollClient(backend=backend, ingress_url="http://test")

    mock_http_client = AsyncMock()
    mock_http_client.post = AsyncMock(side_effect=Exception("connection refused"))

    result = await client._post_event(mock_http_client, raw)
    assert result is False
    assert client._events_sent == 0
