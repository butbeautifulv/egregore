from __future__ import annotations

from typing import Any

import httpx

from connectors.siem_poll.models import SiemRawAlert, normalize_siem_alert
from cys_core.domain.events.models import SecurityEvent
from cys_core.domain.security.exceptions import SecurityViolation
from cys_core.domain.security.factory import get_input_sanitizer
from cys_core.domain.security.sanitizer import InputSanitizer


class SiemPollClient:
    """Poll a SIEM HTTP API and POST normalized events to the ingress API."""

    def __init__(
        self,
        *,
        siem_base_url: str,
        ingress_url: str,
        api_key: str = "",
        siem_token: str = "",
        source: str = "siem_poll",
        sanitizer: InputSanitizer | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.siem_base_url = siem_base_url.rstrip("/")
        self.ingress_url = ingress_url.rstrip("/")
        self.api_key = api_key
        self.siem_token = siem_token
        self.source = source
        self.sanitizer = sanitizer or get_input_sanitizer()
        self._client = client
        self._owns_client = client is None

    async def __aenter__(self) -> SiemPollClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, *args: object) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    def _siem_headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.siem_token:
            headers["Authorization"] = f"Bearer {self.siem_token}"
        return headers

    def _ingress_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    async def fetch_alerts(self, *, since: str | None = None) -> list[SiemRawAlert]:
        """Fetch new alerts from the SIEM search/notable endpoint."""
        client = self._client
        if client is None:
            raise RuntimeError("SiemPollClient is not open; use async with")
        params: dict[str, str] = {}
        if since:
            params["since"] = since
        response = await client.get(
            f"{self.siem_base_url}/alerts",
            headers=self._siem_headers(),
            params=params,
        )
        response.raise_for_status()
        data = response.json()
        records = _extract_alert_records(data)
        return [SiemRawAlert.from_siem_record(record) for record in records]

    def sanitize_event(self, event: SecurityEvent) -> SecurityEvent | None:
        """Sanitize event payload before ingress. Returns None if hard injection detected."""
        try:
            sanitized_payload = self.sanitizer.sanitize_payload(event.payload, source="external")
            return event.model_copy(update={"payload": sanitized_payload})
        except SecurityViolation:
            return None

    def event_to_ingress_body(self, event: SecurityEvent) -> dict[str, Any]:
        return {
            "event_type": event.type,
            "payload": event.payload,
            "severity": event.severity,
            "source": event.source,
            "event_id": event.id,
            "correlation_id": event.correlation_id,
        }

    async def post_event(self, event: SecurityEvent) -> dict[str, Any]:
        client = self._client
        if client is None:
            raise RuntimeError("SiemPollClient is not open; use async with")
        response = await client.post(
            f"{self.ingress_url}/events",
            headers=self._ingress_headers(),
            json=self.event_to_ingress_body(event),
        )
        response.raise_for_status()
        return response.json()

    async def poll_once(self, *, since: str | None = None) -> list[dict[str, Any]]:
        """Fetch alerts, sanitize, and forward to ingress. Skips poisoned alerts."""
        results: list[dict[str, Any]] = []
        for alert in await self.fetch_alerts(since=since):
            event = normalize_siem_alert(alert, source=self.source)
            safe_event = self.sanitize_event(event)
            if safe_event is None:
                continue
            results.append(await self.post_event(safe_event))
        return results


def _extract_alert_records(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    if not isinstance(data, dict):
        return []
    for key in ("results", "alerts", "data", "items"):
        value = data.get(key)
        if isinstance(value, list):
            return [r for r in value if isinstance(r, dict)]
    return []
