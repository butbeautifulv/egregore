from __future__ import annotations

from typing import Any

from cys_core.infrastructure.http_client import request_json
from bootstrap.settings import get_settings


def _mock_search(*, query: str, time_range: str, limit: int) -> dict[str, Any]:
    capped = max(1, min(limit, 100))
    return {
        "query": query,
        "time_range": time_range,
        "limit": capped,
        "result_count": min(2, capped),
        "readonly": True,
        "adapter": "mock",
        "results": [
            {
                "timestamp": "2026-06-11T10:00:00Z",
                "host": "ws-01",
                "rule": "Suspicious PowerShell",
                "message": f"Encoded command matching query: {query}",
                "severity": "high",
            },
            {
                "timestamp": "2026-06-11T10:05:00Z",
                "host": "ws-01",
                "rule": "Lateral movement",
                "message": f"Related auth event for query: {query}",
                "severity": "medium",
            },
        ],
    }


def _http_search(*, query: str, time_range: str, limit: int, base_url: str) -> dict[str, Any]:
    capped = max(1, min(limit, 100))
    url = f"{base_url.rstrip('/')}/search"
    response = request_json(
        "GET",
        url,
        timeout=10.0,
        params={"q": query, "time_range": time_range, "limit": capped, "readonly": "true"},
    )
    response.raise_for_status()
    data = response.json()
    if isinstance(data, dict):
        data.setdefault("adapter", "http")
        data.setdefault("readonly", True)
        return data
    return {
        "query": query,
        "time_range": time_range,
        "limit": capped,
        "readonly": True,
        "adapter": "http",
        "results": data,
    }


def query_siem_readonly_search(
    *,
    query: str,
    time_range: str = "24h",
    limit: int = 50,
) -> dict[str, Any]:
    """Read-only SIEM search — mock by default, HTTP when SIEM_ADAPTER=http."""
    settings = get_settings()
    capped = max(1, min(limit, 100))
    if settings.siem_adapter.lower() == "http" and settings.siem_base_url:
        return _http_search(query=query, time_range=time_range, limit=capped, base_url=settings.siem_base_url)
    return _mock_search(query=query, time_range=time_range, limit=capped)
