from __future__ import annotations

import pytest

from cys_core.domain.parsing.json_text import parse_json_text, parse_loose_structured_text


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


@pytest.mark.unit
def test_parse_loose_structured_text_python_repr_prefix():
    text = (
        "Returning structured response: personas=[] sub_goals={} rationale='' "
        "reasoning_steps=[] plan_status='' execution_mode=None synthesis_persona=None"
    )
    parsed = parse_loose_structured_text(text)
    assert parsed is not None
    assert parsed["personas"] == []
    assert parsed["sub_goals"] == {}
    assert parsed["rationale"] == ""
    assert parsed["execution_mode"] is None
    assert parsed["synthesis_persona"] is None


@pytest.mark.unit
def test_parse_loose_structured_text_with_personas():
    text = (
        "Returning structured response: personas=['consultant'] "
        "sub_goals={'consultant': 'explain CI/CD'} rationale='advisory' "
        "reasoning_steps=[] plan_status='ok' execution_mode='parallel' synthesis_persona=None"
    )
    parsed = parse_loose_structured_text(text)
    assert parsed is not None
    assert parsed["personas"] == ["consultant"]
    assert parsed["sub_goals"]["consultant"] == "explain CI/CD"
    assert parsed["execution_mode"] == "parallel"
