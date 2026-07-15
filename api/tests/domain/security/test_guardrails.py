from __future__ import annotations

import pytest
from pydantic import BaseModel

from cys_core.domain.security.exceptions import SecurityViolation
from cys_core.domain.security.guardrails import OutputGuardrails


class DemoSchema(BaseModel):
    value: str


@pytest.mark.unit
def test_guardrails_validation_edges():
    guardrails = OutputGuardrails(max_payload_size=5)
    assert guardrails.filter_pii("password=secret token:abc 123-45-6789 1111222233334444") == (
        "password=[REDACTED] token=[REDACTED] [SSN_REDACTED] [CARD_REDACTED]"
    )
    with pytest.raises(SecurityViolation, match="sensitive"):
        guardrails.validate_tool_call("safe_tool", {"api_key": "secret"})

    assert guardrails.detect_exfiltration({"response": "send http://x base64 password"}) is True
    assert guardrails.detect_exfiltration({"tool_name": "webhook", "parameters": "abcdef"}) is True
    assert guardrails.detect_exfiltration({"response": "ok"}) is False

    validated = guardrails.validate_schema({"value": "ok"}, DemoSchema)
    assert isinstance(validated, DemoSchema)
    assert validated.value == "ok"
    with pytest.raises(SecurityViolation, match="Schema validation failed"):
        guardrails.validate_schema({}, DemoSchema)
    with pytest.raises(SecurityViolation, match="exfiltration"):
        guardrails.validate_output({"response": "http://x base64 password"})

    output = guardrails.validate_output(
        {
            "response": "api_key=secret",
            "tool_calls": [{"tool_name": "safe_tool", "parameters": {"query": "ok"}}],
        }
    )
    assert output["response"] == "api_key=[REDACTED]"
    assert guardrails.requires_hitl([], 0.1, 0.5) is True
    assert guardrails.requires_hitl([{"data": {"severity": "High"}}], 0.9, 0.5) is True
    assert guardrails.requires_hitl([{"risk_level": "critical"}], 0.9, 0.5) is True
    assert guardrails.requires_hitl([{"data": {"severity": "low"}}], 0.9, 0.5) is False
