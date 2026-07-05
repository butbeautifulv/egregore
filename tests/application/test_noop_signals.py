from __future__ import annotations

import pytest

from cys_core.application.workers.noop_signals import (
    NoopClass,
    classify_finding,
    is_noop_finding,
    semantic_dedup_key,
)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("finding", "expected"),
    [
        ({"suppressed": True, "summary": "dup"}, NoopClass.SUPPRESSED),
        ({"response": "duplicate_suppressed", "confidence": 0.15}, NoopClass.DUPLICATE),
        ({"status": "pending_data", "confidence": 0.15}, NoopClass.PENDING_DATA),
        ({"status": "unchanged", "trust_score": 0.2}, NoopClass.PENDING_DATA),
        ({"analysis_type": "network_duplicate_suppression"}, NoopClass.DUPLICATE),
        (
            {"summary": "[UNTRUSTED PENDING] duplicate handoff", "confidence": 0.1},
            NoopClass.PENDING_DATA,
        ),
        ({"summary": "real alert with IOC details", "confidence": 0.9}, None),
    ],
)
def test_classify_finding_cases(finding: dict, expected: NoopClass | None) -> None:
    assert classify_finding(finding) == expected
    assert is_noop_finding(finding) == (expected is not None)


@pytest.mark.unit
def test_semantic_dedup_key_from_envelope_payload() -> None:
    payload = {
        "correlation_id": "eng-f3cb965ffc6a",
        "data": {
            "response": "duplicate_suppressed",
            "event_id": "evt-1",
            "confidence": 0.15,
        },
    }
    key = semantic_dedup_key(payload)
    assert key is not None
    assert "duplicate" in key
    assert "evt-1" in key


@pytest.mark.unit
def test_duplicate_summary_with_marker_and_low_confidence() -> None:
    finding = {
        "summary": "Finding is a duplicate of prior soc analysis",
        "confidence": 0.2,
    }
    assert classify_finding(finding) == NoopClass.PENDING_DATA
