from __future__ import annotations

import base64
from datetime import datetime

from cys_core.domain.engagement.pagination import InvalidListCursor


def encode_cursor(updated_at: datetime, engagement_id: str) -> str:
    ts = updated_at.isoformat()
    payload = f"{ts}|{engagement_id}"
    return base64.urlsafe_b64encode(payload.encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        ts_str, engagement_id = raw.split("|", 1)
        if not engagement_id.strip():
            raise InvalidListCursor("missing engagement_id")
        updated_at = datetime.fromisoformat(ts_str)
        return updated_at, engagement_id
    except InvalidListCursor:
        raise
    except Exception as exc:
        raise InvalidListCursor(str(exc)) from exc


def page_next_cursor(
    rows: list[tuple[datetime, str]],
    *,
    limit: int,
) -> tuple[list[tuple[datetime, str]], str | None]:
    """Given rows of (updated_at, engagement_id) already sorted DESC, return page + next_cursor."""
    has_more = len(rows) > limit
    page = rows[:limit]
    next_cursor: str | None = None
    if has_more and page:
        last_ts, last_id = page[-1]
        next_cursor = encode_cursor(last_ts, last_id)
    return page, next_cursor
