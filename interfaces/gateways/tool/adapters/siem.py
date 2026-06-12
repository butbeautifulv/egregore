from __future__ import annotations

from typing import Any


def query_siem_readonly_search(
    *,
    query: str,
    time_range: str = "24h",
    limit: int = 50,
) -> dict[str, Any]:
    """Mock read-only SIEM search — production replaces with Splunk/Elastic API."""
    capped = max(1, min(limit, 100))
    return {
        "query": query,
        "time_range": time_range,
        "limit": capped,
        "result_count": min(2, capped),
        "readonly": True,
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
