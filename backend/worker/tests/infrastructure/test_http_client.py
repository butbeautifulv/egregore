from __future__ import annotations

import httpx
import pytest

from cys_core.infrastructure.config.infra_settings import configure_http_timeouts, get_http_timeouts
from cys_core.infrastructure.http_client import default_timeout, sync_http_client


@pytest.fixture(autouse=True)
def _wired_http_timeouts():
    """Normally wired by Container._wire_infra_settings from Settings
    (connect_s=5.0 default) at api/worker startup — contracts has no
    Container of its own, so this test wires it directly instead of relying
    on ambient state left behind by another test."""
    previous = get_http_timeouts()
    configure_http_timeouts(connect_s=5.0, read_s=30.0)
    yield
    configure_http_timeouts(connect_s=previous.connect_s, read_s=previous.read_s)


def test_default_timeout_uses_shared_defaults() -> None:
    timeout = default_timeout(total=12.0)
    assert timeout.read == 12.0
    assert timeout.connect == 5.0


def test_sync_http_client_context_manager() -> None:
    with sync_http_client(timeout=1.0) as client:
        assert isinstance(client, httpx.Client)
