from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, ValidationError

from cys_core.domain.security.exceptions import SecurityViolation
from cys_core.domain.security.redaction import RedactionService

SENSITIVE_PARAM_PATTERNS = [
    r"api[_-]?key",
    r"password",
    r"secret",
    r"token",
    r"credential",
    r"private[_-]?key",
    r"парол\w*",
    r"токен\w*",
    r"секрет\w*",
    r"ключ\w*",
]

PROMPT_LEAKAGE_PATTERNS = [
    r"SYSTEM\s*:\s*You\s+are",
    r"SYSTEM_INSTRUCTIONS:",
    r"SECURITY_RULES:",
    r"GLOBAL_RULES:",
    r"instructions?\s*:\s*\d+\.",
    r"ПРАВИЛА_БЕЗОПАСНОСТИ",
    r"СИСТЕМНЫЕ_ИНСТРУКЦИИ",
    r"ГЛОБАЛЬНЫЕ_ПРАВИЛА",
    r"SECURITY_RULES\s*:",
    r"СИСТЕМН\w*\s*:\s*Ты\s+",
]


class OutputGuardrails:
    """Validate and filter agent outputs."""

    def __init__(self, max_payload_size: int = 10_000) -> None:
        self.max_payload_size = max_payload_size
        self._redaction = RedactionService()

    def filter_pii(self, text: str) -> str:
        return self._redaction.redact_pii(text)

    def validate_tool_call(self, tool_name: str, parameters: dict[str, Any]) -> None:
        params_str = json.dumps(parameters).lower()
        for pattern in SENSITIVE_PARAM_PATTERNS:
            if re.search(pattern, params_str):
                raise SecurityViolation("Parameters contain potentially sensitive data")

    def detect_prompt_leakage(self, text: str) -> bool:
        return any(re.search(pattern, text, re.IGNORECASE) for pattern in PROMPT_LEAKAGE_PATTERNS)

    def detect_exfiltration(self, output: dict[str, Any]) -> bool:
        tool_name = output.get("tool_name", "")
        params = output.get("parameters", {})
        blob = str(output).lower()
        if "http" in blob and any(p in blob for p in ("base64", "encode", "password", "парол")):
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
            response_text = str(agent_output["response"])
            if self.detect_prompt_leakage(response_text):
                raise SecurityViolation("Potential system prompt leakage detected")
            agent_output["response"] = self.filter_pii(response_text)
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
