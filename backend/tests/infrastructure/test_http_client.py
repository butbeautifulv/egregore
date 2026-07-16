from __future__ import annotations

import httpx

from cys_core.infrastructure.http_client import default_timeout, sync_http_client


def test_default_timeout_uses_shared_defaults() -> None:
    timeout = default_timeout(total=12.0)
    assert timeout.read == 12.0
    assert timeout.connect == 5.0


def test_sync_http_client_context_manager() -> None:
    with sync_http_client(timeout=1.0) as client:
        assert isinstance(client, httpx.Client)
