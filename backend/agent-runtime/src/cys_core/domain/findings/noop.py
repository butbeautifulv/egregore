from __future__ import annotations

from enum import StrEnum
from typing import Any


class NoopClass(StrEnum):
    DUPLICATE = "duplicate"
    PENDING_DATA = "pending_data"
    SUPPRESSED = "suppressed"
    NO_CHANGE = "no_change"


_NOOP_RESPONSES = frozenset({"duplicate_suppressed", "duplicate", "no_change", "unchanged"})
_NOOP_STATUSES = frozenset({"pending_data", "duplicate_suppressed", "no_change", "unchanged"})
_LOW_CONFIDENCE_STATUSES = frozenset({"pending_data", "unchanged"})
_DEFAULT_NOOP_LOW_CONFIDENCE_THRESHOLD = 0.25
_DEFAULT_NOOP_PENDING_TRUST_THRESHOLD = 0.3
_DEDUP_SUMMARY_MARKERS = (
    "дубликат",
    "дедупликац",
    "duplicate",
    "dedup",
    "не содержит новых",
    "no new data",
    "not contain new",
)
_DEDUP_SUMMARY_PHRASES = (
    "не содержит новых",
    "no new data",
    "признано дубликатом",
    "duplicate suppressed",
    "duplicate_suppressed",
    "ситуация не изменилась",
    "unchanged",
)


def _coerce_finding_dict(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    return None


def _finding_body(payload_or_finding: dict[str, Any]) -> dict[str, Any]:
    """Resolve finding fields from envelope payload or flat finding dict."""
    nested = payload_or_finding.get("data")
    if isinstance(nested, dict):
        return nested
    return payload_or_finding


def _event_id_from(payload_or_finding: dict[str, Any], finding: dict[str, Any]) -> str:
    return str(
        finding.get("event_id")
        or payload_or_finding.get("event_id")
        or payload_or_finding.get("correlation_id")
        or finding.get("correlation_id")
        or ""
    )


def _low_confidence(value: Any, *, threshold: float | None = None) -> bool:
    if threshold is None:
        threshold = _DEFAULT_NOOP_LOW_CONFIDENCE_THRESHOLD
    if not isinstance(value, (int, float)):
        return False
    return float(value) <= threshold


def _has_dedup_marker(summary: str) -> bool:
    lowered = summary.lower()
    return any(marker in lowered for marker in _DEDUP_SUMMARY_MARKERS)


def _is_duplicate_summary(summary: str) -> bool:
    lowered = summary.lower()
    if not _has_dedup_marker(lowered):
        return False
    return any(phrase in lowered for phrase in _DEDUP_SUMMARY_PHRASES)


def _is_untrusted_pending_summary(summary: str) -> bool:
    lowered = summary.lower()
    return "untrusted" in lowered and "pending" in lowered


def classify_finding(result: dict[str, Any]) -> NoopClass | None:
    """Classify a worker finding as noop, or None if it should propagate."""
    finding = _coerce_finding_dict(result)
    if finding is None:
        return None

    if finding.get("suppressed") is True:
        return NoopClass.SUPPRESSED

    response = str(finding.get("response", "")).lower()
    if response in _NOOP_RESPONSES:
        if response in ("no_change", "unchanged"):
            return NoopClass.NO_CHANGE
        return NoopClass.DUPLICATE

    status = str(finding.get("status", "")).lower()
    confidence = finding.get("confidence")
    trust_score = finding.get("trust_score")

    if status in _NOOP_STATUSES and _low_confidence(confidence):
        return NoopClass.PENDING_DATA

    if status in _LOW_CONFIDENCE_STATUSES and _low_confidence(
        trust_score,
        threshold=_DEFAULT_NOOP_PENDING_TRUST_THRESHOLD,
    ):
        return NoopClass.PENDING_DATA

    analysis_type = str(finding.get("analysis_type", ""))
    if analysis_type.endswith("_duplicate_suppression"):
        return NoopClass.DUPLICATE

    summary = str(finding.get("summary", ""))
    if summary:
        if _is_untrusted_pending_summary(summary):
            return NoopClass.PENDING_DATA
        if _is_duplicate_summary(summary):
            return NoopClass.DUPLICATE
        if _has_dedup_marker(summary) and _low_confidence(confidence):
            return NoopClass.PENDING_DATA

    return None


def is_noop_finding(result: dict[str, Any]) -> bool:
    """True when a worker finding should not fan out on bus or grow engagement state."""
    return classify_finding(result) is not None


def semantic_dedup_key(payload: dict[str, Any]) -> str | None:
    """Stable key for cross-agent bus dedup of stale / duplicate handoffs."""
    if not isinstance(payload, dict):
        return None
    finding = _finding_body(payload)
    event_id = _event_id_from(payload, finding)
    if not event_id:
        return None

    noop = classify_finding(finding)
    if noop is not None:
        return f"semantic:{noop.value}:{event_id}"

    response = str(finding.get("response", "")).lower()
    if response in _NOOP_RESPONSES:
        return f"semantic:response:{event_id}:{response}"

    status = str(finding.get("status", "")).lower()
    if status in ("pending_data", "duplicate_suppressed", "no_change", "unchanged"):
        if _low_confidence(finding.get("confidence")):
            return f"semantic:pending_data:{event_id}"

    analysis_type = str(finding.get("analysis_type", ""))
    if analysis_type.endswith("_duplicate_suppression"):
        return f"semantic:analysis:{event_id}:{analysis_type}"

    summary = str(finding.get("summary", "")).lower()
    if summary and (_is_duplicate_summary(summary) or _is_untrusted_pending_summary(summary)):
        return f"semantic:dup_summary:{event_id}"

    return None


def revision_semantic_dedup_key(
    *,
    engagement_id: str,
    recipient: str,
    event_id: str = "",
) -> str | None:
    """One revision per persona+event per TTL window."""
    if not engagement_id or not recipient:
        return None
    event_part = event_id or engagement_id
    return f"semantic:revision:{engagement_id}:{recipient}:{event_part}"
