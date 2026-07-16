import pytest

from cys_core.domain.security.redaction import RedactionService


@pytest.mark.unit
def test_redact_pii_password_and_ssn():
    service = RedactionService()
    result = service.redact_pii("password=secret 123-45-6789")
    assert "password=[REDACTED]" in result
    assert "[SSN_REDACTED]" in result


@pytest.mark.unit
def test_redact_sensitive_keys_nested():
    service = RedactionService()
    result = service.redact_sensitive_keys({"api_key": "x", "nested": {"token": "y", "ok": 1}})
    assert result["api_key"] == "***REDACTED***"
    assert result["nested"]["token"] == "***REDACTED***"
    assert result["nested"]["ok"] == 1


@pytest.mark.unit
def test_contains_sensitive_data():
    service = RedactionService()
    assert service.contains_sensitive_data("api_key=abc")
    assert not service.contains_sensitive_data("normal log line")
