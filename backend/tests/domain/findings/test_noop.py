from __future__ import annotations

import json

import pytest

from cys_core.domain.findings.noop import (
    NoopClass,
    classify_finding,
    is_noop_finding,
    revision_semantic_dedup_key,
    semantic_dedup_key,
)


@pytest.mark.unit
def test_classify_finding_suppressed_flag() -> None:
    assert classify_finding({"suppressed": True}) == NoopClass.SUPPRESSED


@pytest.mark.unit
def test_classify_finding_duplicate_response() -> None:
    assert classify_finding({"response": "duplicate_suppressed"}) == NoopClass.DUPLICATE


@pytest.mark.unit
def test_classify_finding_no_change_response() -> None:
    assert classify_finding({"response": "no_change"}) == NoopClass.NO_CHANGE


@pytest.mark.unit
def test_classify_finding_pending_data_low_confidence() -> None:
    finding = {"status": "pending_data", "confidence": 0.1}
    assert classify_finding(finding) == NoopClass.PENDING_DATA


@pytest.mark.unit
def test_classify_finding_duplicate_summary_marker() -> None:
    finding = {"summary": "Finding recognized as duplicate suppressed for event"}
    assert classify_finding(finding) == NoopClass.DUPLICATE


@pytest.mark.unit
def test_classify_finding_propagates_actionable_finding() -> None:
    finding = {"summary": "New IOC cluster identified", "confidence": 0.8}
    assert classify_finding(finding) is None
    assert is_noop_finding(finding) is False


@pytest.mark.unit
def test_semantic_dedup_key_for_noop_finding() -> None:
    payload = {"event_id": "evt-1", "summary": "duplicate suppressed", "confidence": 0.1}
    key = semantic_dedup_key(payload)
    assert key == "semantic:duplicate:evt-1"


@pytest.mark.unit
def test_semantic_dedup_key_for_response_duplicate() -> None:
    payload = {"event_id": "evt-2", "response": "duplicate"}
    assert semantic_dedup_key(payload) == "semantic:duplicate:evt-2"


@pytest.mark.unit
def test_revision_semantic_dedup_key_requires_ids() -> None:
    assert revision_semantic_dedup_key(engagement_id="", recipient="soc") is None
    key = revision_semantic_dedup_key(engagement_id="eng-1", recipient="soc", event_id="evt-3")
    assert key == "semantic:revision:eng-1:soc:evt-3"


@pytest.mark.unit
def test_semantic_dedup_key_unwraps_nested_envelope_data() -> None:
    envelope = {
        "data": {"response": "unchanged", "confidence": 0.1},
        "event_id": "evt-4",
    }
    # classify_finding reads flat dict only; semantic_dedup_key unwraps envelope data.
    assert classify_finding(envelope) is None
    assert semantic_dedup_key(envelope) == "semantic:no_change:evt-4"


@pytest.mark.unit
def test_classify_finding_analysis_type_duplicate_suppression() -> None:
    finding = {"analysis_type": "soc_duplicate_suppression", "summary": "dup"}
    assert classify_finding(finding) == NoopClass.DUPLICATE


@pytest.mark.unit
def test_classify_finding_untrusted_pending_summary() -> None:
    finding = {"summary": "Source is untrusted and pending enrichment"}
    assert classify_finding(finding) == NoopClass.PENDING_DATA


@pytest.mark.unit
def test_classify_finding_non_dict_returns_none() -> None:
    assert classify_finding(json.loads('["not", "a", "dict"]')) is None
