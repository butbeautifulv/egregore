from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from interfaces.control_plane.postgres_status_store import PostgresStatusStore


@pytest.mark.unit
def test_postgres_status_store_records_and_snapshots():
    payloads: list[tuple[str, str]] = []

    class FakeCursor:
        def execute(self, query, params=None):
            if params and "INSERT" in query:
                payloads.append((params[0], params[1]))

        def fetchall(self):
            return [({"text": "narrative"},), ({"event_id": "e1"},)]

    class FakeConn:
        def execute(self, query, params=None):
            pass

        def commit(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def cursor(self):
            return FakeCursor()

    with patch("interfaces.control_plane.postgres_status_store.psycopg.connect") as connect:
        connect.return_value = FakeConn()
        store = PostgresStatusStore("postgresql://localhost/test")
        store._fetch_recent = MagicMock(  # type: ignore[method-assign]
            side_effect=lambda kind, limit: {
                "event": [{"id": "e1"}],
                "finding": [],
                "critic": [],
                "narrative": [{"text": "hello"}],
                "awaiting_approval": [],
                "escalation": [],
            }[kind]
        )
        store.record_event({"id": "e1"})
        snap = store.snapshot()
        assert snap["events_count"] == 1
        assert snap["latest_narrative"] == "hello"
