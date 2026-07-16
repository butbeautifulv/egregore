from __future__ import annotations

import json

import pytest

from cys_core.domain.findings.normalize import (
    normalize_finding_payload,
    normalize_list_field,
    structured_has_content,
)


@pytest.mark.unit
def test_normalize_finding_payload_unwraps_nested_finding() -> None:
    wrapped = {"finding": {"summary": "done", "iocs": ["1.2.3.4"]}}
    out = normalize_finding_payload(wrapped)
    assert out["summary"] == "done"
    assert out["iocs"] == ["1.2.3.4"]


@pytest.mark.unit
def test_normalize_finding_payload_unwraps_data_envelope() -> None:
    wrapped = {"data": {"summary": "intel hit", "topic": "phishing"}}
    out = normalize_finding_payload(wrapped)
    assert out["summary"] == "intel hit"


@pytest.mark.unit
def test_normalize_finding_payload_parses_json_content() -> None:
    payload = {"content": json.dumps({"summary": "from json", "severity": "low"})}
    out = normalize_finding_payload(payload)
    assert out["summary"] == "from json"


@pytest.mark.unit
def test_normalize_finding_payload_preserves_error_payload() -> None:
    payload = {"error": "validation failed"}
    assert normalize_finding_payload(payload) == payload


@pytest.mark.unit
def test_structured_has_content_detects_nonempty_fields() -> None:
    assert structured_has_content({"summary": "text"}) is True
    assert structured_has_content({"items": []}) is False
    assert structured_has_content({"count": 3}) is True
    assert structured_has_content({"count": 0}) is False


@pytest.mark.unit
def test_normalize_list_field_coerces_string_and_filters_invalid() -> None:
    data: dict[str, object] = {"recommendations": " one ", "references": 123}
    normalize_list_field(data, "recommendations")
    normalize_list_field(data, "references")
    assert data["recommendations"] == ["one"]
    assert "references" not in data


@pytest.mark.unit
def test_normalize_list_field_normalizes_list_items() -> None:
    data = {"recommendations": [" a ", "", "b"]}
    normalize_list_field(data, "recommendations")
    assert data["recommendations"] == ["a", "b"]
