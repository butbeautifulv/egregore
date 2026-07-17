from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from bootstrap.settings import Settings
from cys_core.infrastructure.auth.broker import AuthBrokerOutbound


@pytest.mark.unit
def test_auth_broker_disabled_by_default():
    broker = AuthBrokerOutbound(Settings())
    assert broker.enabled() is False
    with pytest.raises(RuntimeError, match="not configured"):
        broker.get_access_token()


@pytest.mark.unit
def test_auth_broker_fetches_and_caches_token():
    settings = Settings.model_construct(
        use_auth_broker=True,
        auth_broker_url="http://broker.test",
        auth_broker_service_token="svc-token",
        auth_broker_service_id="egregore",
        auth_broker_audience="veil-api",
    )
    broker = AuthBrokerOutbound(settings)
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {"access_token": "tok-1", "expires_in": 120}

    with patch("cys_core.infrastructure.auth.broker.httpx.Client") as client_cls:
        client = MagicMock()
        client.__enter__.return_value = client
        client.post.return_value = response
        client_cls.return_value = client

        token = broker.get_access_token()
        assert token == "tok-1"
        assert broker.authorization_header() == {"Authorization": "Bearer tok-1"}
        client.post.assert_called_once()
