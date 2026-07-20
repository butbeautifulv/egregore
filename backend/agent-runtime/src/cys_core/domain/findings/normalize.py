from __future__ import annotations

from typing import Any

from cys_core.domain.parsing.json_text import parse_json_text


def normalize_finding_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Unwrap common LLM finding envelopes before schema validation."""
    if not isinstance(data, dict) or "error" in data:
        return data

    finding_val = data.get("finding")
    if isinstance(finding_val, dict) and finding_val:
        unwrapped = normalize_finding_payload(finding_val)
        if unwrapped:
            return unwrapped

    for key in ("data", "result", "output"):
        nested = data.get(key)
        if isinstance(nested, dict) and nested:
            unwrapped = normalize_finding_payload(nested)
            if unwrapped and _looks_like_worker_finding(unwrapped):
                return unwrapped

    content_parsed = data.get("content_parsed")
    if isinstance(content_parsed, dict):
        return normalize_finding_payload(content_parsed)

    for key in ("content", "raw_response"):
        raw = data.get(key)
        if isinstance(raw, str) and raw.strip():
            parsed = parse_json_text(raw)
            if isinstance(parsed, dict):
                return normalize_finding_payload(parsed)

    return data


def _looks_like_worker_finding(data: dict[str, Any]) -> bool:
    markers = (
        "summary",
        "topic",
        "hypothesis",
        "iocs",
        "actor_profile",
        "artifacts",
        "identity_asset",
        "cloud_provider",
        "recommendations",
        "severity",
    )
    return any(key in data for key in markers)


def structured_has_content(result: dict[str, Any]) -> bool:
    for value in result.values():
        if isinstance(value, str) and value.strip():
            return True
        if isinstance(value, list) and value:
            return True
        if isinstance(value, (int, float)) and value not in (0, 0.0):
            return True
    return False


def normalize_list_field(data: dict[str, Any], key: str) -> None:
    """Coerce a single string into a one-item list; drop invalid non-list values."""
    if key not in data:
        return
    value = data[key]
    if isinstance(value, str):
        stripped = value.strip()
        data[key] = [stripped] if stripped else []
        return
    if isinstance(value, list):
        data[key] = [str(item).strip() for item in value if str(item).strip()]
        return
    del data[key]
