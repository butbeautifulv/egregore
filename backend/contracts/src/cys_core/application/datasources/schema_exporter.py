from __future__ import annotations

from copy import deepcopy
from typing import Any

from cys_core.application.datasources.model_family import export_options_for_family, knobs_for_model_family
from cys_core.domain.datasources.schema_models import ModelFamily, SchemaExportOptions


def _normalize_required(schema: dict[str, Any], *, normalize_required: bool) -> dict[str, Any]:
    if not normalize_required or schema.get("type") != "object":
        return schema
    props = schema.get("properties")
    if not isinstance(props, dict) or not props:
        return schema
    explicit = schema.get("required")
    if isinstance(explicit, list) and explicit:
        schema["required"] = sorted(set(explicit))
        return schema
    schema["required"] = sorted(props.keys())
    return schema


def _apply_strict_additional_properties(node: Any, *, strict: bool) -> Any:
    if isinstance(node, list):
        return [_apply_strict_additional_properties(item, strict=strict) for item in node]
    if not isinstance(node, dict):
        return node
    out = {key: _apply_strict_additional_properties(value, strict=strict) for key, value in node.items()}
    node_type = out.get("type")
    if strict and node_type == "object" and "additionalProperties" not in out:
        out["additionalProperties"] = False
    if node_type == "object" and isinstance(out.get("properties"), dict):
        out["properties"] = {
            key: _apply_strict_additional_properties(value, strict=strict) for key, value in out["properties"].items()
        }
    return out


def export_json_schema(
    schema: dict[str, Any],
    *,
    options: SchemaExportOptions | None = None,
    family: ModelFamily | str = ModelFamily.GENERIC,
) -> dict[str, Any]:
    opts = options or export_options_for_family(family)
    exported = deepcopy(schema)
    exported = _apply_strict_additional_properties(exported, strict=opts.strict_additional_properties)
    exported = _normalize_required(exported, normalize_required=opts.normalize_required)
    return exported


def export_for_family(schema: dict[str, Any], family: ModelFamily | str) -> dict[str, Any]:
    _ = knobs_for_model_family(family)
    return export_json_schema(schema, family=family)
