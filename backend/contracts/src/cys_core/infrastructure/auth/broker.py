from __future__ import annotations

import httpx

from bootstrap.settings import Settings


class AuthBrokerOutbound:
    """Fetch OAuth2 access tokens from cxado auth-broker for outbound API calls."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._cache: dict[tuple[str, tuple[str, ...]], tuple[str, float]] = {}

    def enabled(self) -> bool:
        return bool(
            self._settings.use_auth_broker
            and self._settings.auth_broker_url.strip()
            and self._settings.auth_broker_service_token.strip()
        )

    def get_access_token(self, audience: str | None = None, scopes: list[str] | None = None) -> str:
        if not self.enabled():
            raise RuntimeError("auth broker is not configured")
        aud = (audience or self._settings.auth_broker_audience).strip()
        scope_list = scopes or []
        cache_key = (aud, tuple(scope_list))
        import time

        cached = self._cache.get(cache_key)
        if cached is not None:
            token, expires_at = cached
            if time.monotonic() < expires_at:
                return token

        url = self._settings.auth_broker_url.rstrip("/") + "/v1/token"
        headers = {
            "Authorization": f"Bearer {self._settings.auth_broker_service_token}",
            "Content-Type": "application/json",
            "X-Service-Id": self._settings.auth_broker_service_id,
        }
        payload = {"audience": aud, "scopes": scope_list}
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        token = str(data.get("access_token", "")).strip()
        if not token:
            raise RuntimeError("auth broker returned empty access_token")
        expires_in = int(data.get("expires_in", 60))
        self._cache[cache_key] = (token, time.monotonic() + max(expires_in - 30, 1))
        return token

    def authorization_header(self, audience: str | None = None) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.get_access_token(audience=audience)}"}
