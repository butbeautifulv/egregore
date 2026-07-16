from __future__ import annotations

import pytest

from cys_core.domain.tools.coercion import (
    VALID_TI_CATEGORIES,
    coerce_tool_args,
    normalize_technique_id,
    normalize_ti_category,
)


@pytest.mark.unit
def test_normalize_technique_id_accepts_attack_format() -> None:
    assert normalize_technique_id("t1190") == "T1190"
    assert normalize_technique_id("1190.001") == "T1190.001"


@pytest.mark.unit
def test_normalize_technique_id_rejects_non_string() -> None:
    assert normalize_technique_id(1190) == ""


@pytest.mark.unit
def test_normalize_ti_category_aliases() -> None:
    assert normalize_ti_category("IOCs") == "ti"
    assert normalize_ti_category("mitre_attack") == "mitre"
    assert normalize_ti_category("playbooks") == "playbook"


@pytest.mark.unit
def test_normalize_ti_category_unknown_passthrough() -> None:
    assert normalize_ti_category("sbom") == "sbom"
    assert normalize_ti_category("sbom") in VALID_TI_CATEGORIES


@pytest.mark.unit
def test_coerce_tool_args_parses_scalar_strings() -> None:
    args = coerce_tool_args({"limit": "5", "enabled": "true", "name": "scan"})
    assert args == {"limit": 5, "enabled": True, "name": "scan"}


@pytest.mark.unit
def test_coerce_tool_args_parses_json_strings() -> None:
    args = coerce_tool_args({"filters": '["a", "b"]', "meta": '{"k": 1}'})
    assert args["filters"] == ["a", "b"]
    assert args["meta"] == {"k": 1}


@pytest.mark.unit
def test_coerce_tool_args_invalid_json_keeps_original() -> None:
    raw = "[not json"
    assert coerce_tool_args({"filters": raw})["filters"] == raw


@pytest.mark.unit
def test_coerce_tool_args_recurses_nested_structures() -> None:
    nested = {"outer": {"inner": "42"}, "items": ["1", "false"]}
    coerced = coerce_tool_args(nested)
    assert coerced == {"outer": {"inner": 42}, "items": [1, False]}
