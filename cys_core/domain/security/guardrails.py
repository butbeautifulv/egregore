from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, ValidationError

from cys_core.domain.security.exceptions import SecurityViolation

PII_PATTERNS = [
    (r"\b\d{3}-\d{2}-\d{4}\b", "[SSN_REDACTED]"),
    (r"\b\d{16}\b", "[CARD_REDACTED]"),
    (r"password\s*[:=]\s*\S+", "password=[REDACTED]"),
    (r"api[_-]?key\s*[:=]\s*\S+", "api_key=[REDACTED]"),
    (r"secret\s*[:=]\s*\S+", "secret=[REDACTED]"),
    (r"token\s*[:=]\s*\S+", "token=[REDACTED]"),
]

SENSITIVE_PARAM_PATTERNS = [
    r"api[_-]?key",
    r"password",
    r"secret",
    r"token",
    r"credential",
    r"private[_-]?key",
]


class OutputGuardrails:
    """Validate and filter agent outputs."""

    def __init__(
        self,
        allowed_tools: set[str] | None = None,
        max_payload_size: int = 10_000,
    ) -> None:
        self.allowed_tools = allowed_tools
        self.max_payload_size = max_payload_size

    def filter_pii(self, text: str) -> str:
        for pattern, replacement in PII_PATTERNS:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        return text

    def validate_tool_call(self, tool_name: str, parameters: dict[str, Any]) -> None:
        if self.allowed_tools is not None and tool_name not in self.allowed_tools:
            raise SecurityViolation(f"Tool '{tool_name}' is not in allowed list")
        params_str = json.dumps(parameters).lower()
        for pattern in SENSITIVE_PARAM_PATTERNS:
            if re.search(pattern, params_str):
                raise SecurityViolation("Parameters contain potentially sensitive data")

    def detect_exfiltration(self, output: dict[str, Any]) -> bool:
        tool_name = output.get("tool_name", "")
        params = output.get("parameters", {})
        blob = str(output).lower()
        if "http" in blob and any(p in blob for p in ("base64", "encode", "password")):
            return True
        if tool_name in ("http_request", "webhook") and len(str(params)) > self.max_payload_size:
            return True
        return False

    def validate_schema(self, data: dict[str, Any], schema: type[BaseModel]) -> BaseModel:
        try:
            return schema.model_validate(data)
        except ValidationError as exc:
            raise SecurityViolation(f"Schema validation failed: {exc}") from exc

    def validate_output(self, agent_output: dict[str, Any]) -> dict[str, Any]:
        if self.detect_exfiltration(agent_output):
            raise SecurityViolation("Potential data exfiltration detected")
        if "response" in agent_output:
            agent_output["response"] = self.filter_pii(str(agent_output["response"]))
        if "tool_calls" in agent_output:
            for call in agent_output["tool_calls"]:
                self.validate_tool_call(call.get("tool_name", ""), call.get("parameters", {}))
        return agent_output

    def requires_hitl(self, findings: list[dict[str, Any]], trust_score: float, threshold: float) -> bool:
        if trust_score < threshold:
            return True
        for finding in findings:
            severity = str(finding.get("data", finding).get("severity", "")).lower()
            if severity in ("critical", "high"):
                return True
            risk = str(finding.get("data", finding).get("risk_level", "")).lower()
            if risk in ("critical", "high"):
                return True
        return False

