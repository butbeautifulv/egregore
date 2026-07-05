from __future__ import annotations

from typing import Any


def structured_has_content(data: dict[str, Any]) -> bool:
    for value in data.values():
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


def normalize_consultant_lists(result: dict[str, Any]) -> None:
    if not result.get("recommendations") and result.get("recommended_actions"):
        result["recommendations"] = result["recommended_actions"]
    normalize_list_field(result, "recommendations")
    normalize_list_field(result, "references")


def _consultant_recommendations(result: dict[str, Any]) -> list[str]:
    recs = result.get("recommendations")
    if isinstance(recs, list):
        return [str(item).strip() for item in recs if str(item).strip()]
    return []


def _consultant_meets_minimum(result: dict[str, Any]) -> bool:
    topic = str(result.get("topic", "")).strip()
    summary = str(result.get("summary", "")).strip()
    recommendations = _consultant_recommendations(result)
    confidence = result.get("confidence", 0)
    try:
        confidence_val = float(confidence)
    except (TypeError, ValueError):
        confidence_val = 0.0
    return bool(topic and summary and len(recommendations) >= 2 and confidence_val > 0)


def finding_meets_minimum(persona: str, result: dict[str, Any], *, schema_name: str | None) -> bool:
    if not schema_name:
        return True
    if "error" in result:
        return False

    if persona == "soc":
        return bool(str(result.get("summary", "")).strip())
    if persona == "intel":
        return bool(str(result.get("summary", "")).strip()) or bool(result.get("iocs"))
    if persona == "hunter":
        return bool(str(result.get("hypothesis", "")).strip()) or bool(str(result.get("summary", "")).strip())
    if persona == "consultant":
        normalize_consultant_lists(result)
        return _consultant_meets_minimum(result)

    return structured_has_content(result)
