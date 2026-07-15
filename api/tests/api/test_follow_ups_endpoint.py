from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from interfaces.api.follow_ups import router


def _follow_up_app(monkeypatch, use_case: MagicMock) -> FastAPI:
    container = MagicMock()
    container.get_enqueue_follow_up.return_value = use_case
    monkeypatch.setattr("interfaces.api.follow_ups.get_container", lambda: container)
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_follow_ups_returns_turns(monkeypatch) -> None:
    use_case = MagicMock()
    use_case.list_turns.return_value = [
        {
            "id": "mem-1",
            "role": "operator",
            "text": "Why?",
            "created_at": "2026-01-01T00:00:00+00:00",
            "follow_up_id": "fu-1",
            "job_id": None,
            "persona": None,
            "status": "completed",
        }
    ]
    app = _follow_up_app(monkeypatch, use_case)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/v1/engagements/eng-1/follow-ups")
        assert resp.status_code == 200
        body = resp.json()
        assert body["turns"][0]["role"] == "operator"
        assert body["turns"][0]["follow_up_id"] == "fu-1"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_post_follow_up_returns_202(monkeypatch) -> None:
    use_case = MagicMock()
    use_case.execute.return_value = {
        "follow_up_id": "fu-abc",
        "status": "queued",
        "work_kind": "follow_up_qa",
        "job_id": "consultant-fu-abc",
    }
    app = _follow_up_app(monkeypatch, use_case)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/v1/engagements/eng-closed/follow-ups",
            json={"message": "Explain the alert", "mode": "qa"},
        )
        assert resp.status_code == 202
        body = resp.json()
        assert body["follow_up_id"] == "fu-abc"
        assert body["status"] == "queued"
