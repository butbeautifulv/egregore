from __future__ import annotations

import pytest

from cys_core.domain.parsing.json_text import parse_json_text


@pytest.mark.unit
def test_parse_json_text_plain_object():
    assert parse_json_text('{"a": 1}') == {"a": 1}


@pytest.mark.unit
def test_parse_json_text_fenced_codeblock():
    text = '```json\n{"incident_id": "i1", "priority": "high"}\n```'
    assert parse_json_text(text) == {"incident_id": "i1", "priority": "high"}


@pytest.mark.unit
def test_parse_json_text_invalid_returns_none():
    assert parse_json_text("not json") is None
    assert parse_json_text("[1, 2]") is None
