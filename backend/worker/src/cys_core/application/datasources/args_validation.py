from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from cys_core.application.datasources.model_family import knobs_for_model_family
from cys_core.application.datasources.schema_fetch import ToolInputSchema
from cys_core.domain.datasources.schema_models import ModelFamily, SchemaMismatchPayload


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int) and not isinstance(value, bool):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _validate_against_json_schema(args: dict[str, Any], schema: dict[str, Any], *, reject_unknown: bool) -> list[str]:
    errors: list[str] = []
    if schema.get("type") != "object":
        return errors
    props = schema.get("properties", {})
    if not isinstance(props, dict):
        return errors
    required = schema.get("required", [])
    if isinstance(required, list):
        for field in required:
            if field not in args:
                errors.append(f"missing required field: {field}")
    if reject_unknown:
        for key in args:
            if key not in props:
                errors.append(f"unknown field: {key}")
    for key, value in args.items():
        spec = props.get(key)
        if not isinstance(spec, dict):
            continue
        expected = spec.get("type")
        if expected and _type_name(value) != expected:
            errors.append(f"{key}: expected {expected}, got {_type_name(value)}")
    return errors


def validate_tool_args(
    args: dict[str, Any],
    schema: ToolInputSchema,
    *,
    family: ModelFamily | str = ModelFamily.GENERIC,
) -> list[str]:
    knobs = knobs_for_model_family(family)
    if schema.pydantic_model is not None:
        try:
            schema.pydantic_model.model_validate(args)
            return []
        except ValidationError as exc:
            return [f"{err['loc']}: {err['msg']}" for err in exc.errors()]
    return _validate_against_json_schema(
        args,
        schema.json_schema,
        reject_unknown=knobs.reject_unknown_args,
    )


def build_schema_mismatch_payload(tool_name: str, errors: list[str]) -> SchemaMismatchPayload:
    return SchemaMismatchPayload(tool_name=tool_name, errors=errors)
