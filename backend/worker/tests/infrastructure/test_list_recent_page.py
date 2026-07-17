from __future__ import annotations

from datetime import UTC, datetime

import pytest

from cys_core.domain.engagement.models import Engagement, EngagementStatus
from cys_core.infrastructure.engagement.list_cursor import (
    InvalidListCursor,
    decode_cursor,
    encode_cursor,
    page_next_cursor,
)
from cys_core.infrastructure.engagement.memory_store import MemoryEngagementStateStore


@pytest.mark.unit
def test_encode_decode_cursor_round_trip() -> None:
    updated = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)
    cursor = encode_cursor(updated, "wo-abc")
    decoded_updated, decoded_id = decode_cursor(cursor)
    assert decoded_id == "wo-abc"
    assert decoded_updated == updated


@pytest.mark.unit
def test_decode_cursor_invalid_raises() -> None:
    with pytest.raises(InvalidListCursor):
        decode_cursor("not-a-valid-cursor")


@pytest.mark.unit
def test_page_next_cursor_has_more() -> None:
    ts = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)
    rows = [(ts, "wo-3"), (ts, "wo-2"), (ts, "wo-1")]
    page, next_cursor = page_next_cursor(rows, limit=2)
    assert page == [(ts, "wo-3"), (ts, "wo-2")]
    assert next_cursor is not None
    assert decode_cursor(next_cursor) == (ts, "wo-2")


@pytest.mark.unit
def test_memory_list_recent_page_empty() -> None:
    store = MemoryEngagementStateStore()
    items, next_cursor = store.list_recent_page("default", limit=20)
    assert items == []
    assert next_cursor is None


@pytest.mark.unit
def test_memory_list_recent_page_pagination_and_tiebreaker() -> None:
    store = MemoryEngagementStateStore()
    base = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)
    for engagement_id in ("wo-a", "wo-b", "wo-c"):
        store.upsert(
            Engagement(
                id=engagement_id,
                tenant_id="default",
                goal=engagement_id,
                status=EngagementStatus.RUNNING,
            )
        )
    store._updated_at["default"]["wo-a"] = base
    store._updated_at["default"]["wo-b"] = base
    store._updated_at["default"]["wo-c"] = base

    page1, cursor1 = store.list_recent_page("default", limit=2)
    assert [eng.id for eng, _ts in page1] == ["wo-c", "wo-b"]
    assert cursor1 is not None

    page2, cursor2 = store.list_recent_page("default", limit=2, cursor=cursor1)
    assert [eng.id for eng, _ts in page2] == ["wo-a"]
    assert cursor2 is None


@pytest.mark.unit
def test_memory_list_recent_page_invalid_cursor() -> None:
    store = MemoryEngagementStateStore()
    with pytest.raises(InvalidListCursor):
        store.list_recent_page("default", limit=2, cursor="bad")
