from __future__ import annotations

import pytest

from cys_core.domain.findings.noop import NoopClass, classify_finding, semantic_dedup_key


@pytest.mark.unit
def test_classify_finding_low_trust_score_pending() -> None:
    finding = {"status": "unchanged", "trust_score": 0.1}
    assert classify_finding(finding) == NoopClass.PENDING_DATA


@pytest.mark.unit
def test_classify_finding_dedup_marker_low_confidence_pending() -> None:
    finding = {"summary": "dedup marker only", "confidence": 0.1}
    assert classify_finding(finding) == NoopClass.PENDING_DATA


@pytest.mark.unit
def test_low_confidence_ignores_non_numeric() -> None:
    finding = {"status": "pending_data", "confidence": "low"}
    assert classify_finding(finding) is None


@pytest.mark.unit
def test_semantic_dedup_key_non_dict_returns_none() -> None:
    assert semantic_dedup_key("not-a-dict") is None  # type: ignore[arg-type]


@pytest.mark.unit
def test_semantic_dedup_key_missing_event_id() -> None:
    assert semantic_dedup_key({"summary": "duplicate suppressed"}) is None


@pytest.mark.unit
def test_semantic_dedup_key_response_branch_for_actionable(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "event_id": "evt-5",
        "summary": "New finding with response marker",
        "response": "unchanged",
        "confidence": 0.9,
    }
    monkeypatch.setattr(
        "cys_core.domain.findings.noop.classify_finding",
        lambda _finding: None,
    )
    assert semantic_dedup_key(payload) == "semantic:response:evt-5:unchanged"


@pytest.mark.unit
def test_semantic_dedup_key_pending_data_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"event_id": "evt-6", "status": "pending_data", "confidence": 0.1}
    monkeypatch.setattr(
        "cys_core.domain.findings.noop.classify_finding",
        lambda _finding: None,
    )
    assert semantic_dedup_key(payload) == "semantic:pending_data:evt-6"


@pytest.mark.unit
def test_semantic_dedup_key_analysis_type_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "event_id": "evt-7",
        "analysis_type": "intel_duplicate_suppression",
        "summary": "actionable",
        "confidence": 0.9,
    }
    monkeypatch.setattr(
        "cys_core.domain.findings.noop.classify_finding",
        lambda _finding: None,
    )
    assert semantic_dedup_key(payload) == "semantic:analysis:evt-7:intel_duplicate_suppression"


@pytest.mark.unit
def test_semantic_dedup_key_dup_summary_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "event_id": "evt-8",
        "summary": "duplicate suppressed for event",
        "confidence": 0.9,
    }
    monkeypatch.setattr(
        "cys_core.domain.findings.noop.classify_finding",
        lambda _finding: None,
    )
    assert semantic_dedup_key(payload) == "semantic:dup_summary:evt-8"


@pytest.mark.unit
def test_semantic_dedup_key_untrusted_summary_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "event_id": "evt-9",
        "summary": "source untrusted pending review",
        "confidence": 0.9,
    }
    monkeypatch.setattr(
        "cys_core.domain.findings.noop.classify_finding",
        lambda _finding: None,
    )
    assert semantic_dedup_key(payload) == "semantic:dup_summary:evt-9"


@pytest.mark.unit
def test_semantic_dedup_key_actionable_returns_none() -> None:
    assert semantic_dedup_key({"event_id": "evt-10", "summary": "brand new IOC", "confidence": 0.9}) is None
