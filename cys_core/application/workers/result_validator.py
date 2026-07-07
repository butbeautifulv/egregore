from __future__ import annotations

from typing import Any

from cys_core.application.ports.schema_registry import SchemaRegistryPort
from cys_core.application.workers.finding_quality import (
    normalize_consultant_lists,
    normalize_finding_payload,
    preserve_planned_tool_calls,
)
from cys_core.domain.security.exceptions import SecurityViolation
from cys_core.domain.security.guardrails import OutputGuardrails


class WorkerResultValidator:
    def __init__(
        self,
        *,
        schema_registry: SchemaRegistryPort,
        guardrails: OutputGuardrails,
        dev_schema_bypass: bool = False,
    ) -> None:
        self._schema_registry = schema_registry
        self._guardrails = guardrails
        self._dev_schema_bypass = dev_schema_bypass

    def validate(self, *, result: dict[str, Any], schema_name: str | None) -> dict[str, Any]:
        if not isinstance(result, dict) or "error" in result:
            return result
        result = normalize_finding_payload(result)
        if isinstance(result.get("reasoning_steps"), list):
            result["sgr_metadata"] = {
                "reasoning_steps": result.get("reasoning_steps"),
                "plan_status": result.get("plan_status", ""),
                "enough_data": result.get("enough_data", False),
            }
        if schema_name == "ConsultantFinding":
            normalize_consultant_lists(result)
        schema = self._schema_registry.get(schema_name or "")
        if schema is None:
            return result
        try:
            validated = self._guardrails.validate_schema(result, schema)
            out = validated.model_dump()
            if "sgr_metadata" in result:
                out["sgr_metadata"] = result["sgr_metadata"]
            return preserve_planned_tool_calls(result, out)
        except SecurityViolation:
            if self._dev_schema_bypass:
                return result
            raise
