from __future__ import annotations

import httpx
import pytest

from cys_core.integrations.mcp_http import acall_with_retry, call_with_retry


def _status_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://mcp.example/mcp")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError("boom", request=request, response=response)


@pytest.mark.unit
def test_call_with_retry_succeeds_after_transient_failures(monkeypatch):
    monkeypatch.setattr("cys_core.integrations.mcp_http.time.sleep", lambda _s: None)
    attempts = {"n": 0}

    def flaky():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise _status_error(503)
        return {"ok": True}

    result = call_with_retry(flaky, max_retries=3, source="test")
    assert result == {"ok": True}
    assert attempts["n"] == 3


@pytest.mark.unit
def test_call_with_retry_raises_after_exhausting_retries(monkeypatch):
    monkeypatch.setattr("cys_core.integrations.mcp_http.time.sleep", lambda _s: None)
    attempts = {"n": 0}

    def always_503():
        attempts["n"] += 1
        raise _status_error(503)

    with pytest.raises(httpx.HTTPStatusError):
        call_with_retry(always_503, max_retries=2, source="test")
    assert attempts["n"] == 3  # initial attempt + 2 retries


@pytest.mark.unit
def test_call_with_retry_does_not_retry_non_transient_status(monkeypatch):
    monkeypatch.setattr("cys_core.integrations.mcp_http.time.sleep", lambda _s: None)
    attempts = {"n": 0}

    def bad_request():
        attempts["n"] += 1
        raise _status_error(400)

    with pytest.raises(httpx.HTTPStatusError):
        call_with_retry(bad_request, max_retries=3, source="test")
    assert attempts["n"] == 1  # no retry — retrying a 400 can't help


@pytest.mark.unit
def test_call_with_retry_retries_connect_timeout(monkeypatch):
    monkeypatch.setattr("cys_core.integrations.mcp_http.time.sleep", lambda _s: None)
    attempts = {"n": 0}

    def flaky():
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise httpx.ConnectTimeout("timed out")
        return {"ok": True}

    result = call_with_retry(flaky, max_retries=2, source="test")
    assert result == {"ok": True}
    assert attempts["n"] == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_acall_with_retry_succeeds_after_transient_failures(monkeypatch):
    monkeypatch.setattr("cys_core.integrations.mcp_http.asyncio.sleep", _async_noop)
    attempts = {"n": 0}

    async def flaky():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise _status_error(429)
        return {"ok": True}

    result = await acall_with_retry(flaky, max_retries=3, source="test")
    assert result == {"ok": True}
    assert attempts["n"] == 3


async def _async_noop(_seconds: float) -> None:
    return None
