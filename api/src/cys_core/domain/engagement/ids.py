from __future__ import annotations

import re
from typing import Any

ENGAGEMENT_ID_RE = re.compile(r"eng-[a-f0-9]{12}")


def extract_engagement_id(*, correlation_id: str = "", payload: dict[str, Any] | None = None) -> str:
    payload = payload or {}
    candidates: list[str] = [correlation_id, str(payload.get("correlation_id", ""))]
    data = payload.get("data")
    if isinstance(data, dict):
        candidates.append(str(data.get("correlation_id", "")))
        candidates.append(str(data.get("incident_id", "")))
    for candidate in candidates:
        match = ENGAGEMENT_ID_RE.search(candidate)
        if match:
            return match.group(0)
    return ""


def normalize_correlation_id(raw: str, payload: dict[str, Any] | None = None) -> str:
    """Return a bare engagement id when wrapped in USER_DATA_TO_PROCESS markup."""
    extracted = extract_engagement_id(correlation_id=raw, payload=payload)
    if extracted:
        return extracted
    return raw.strip()
