import pytest

from cys_core.domain.security.redaction import RedactionService


@pytest.mark.unit
def test_redact_ru_snils_and_secrets():
    service = RedactionService()
    result = service.redact_pii("СНИЛС 123-456-789 01 пароль=секрет123")
    assert "[SNILS_REDACTED]" in result
    assert "пароль=[REDACTED]" in result


@pytest.mark.unit
def test_redact_ru_phone_and_passport():
    service = RedactionService()
    result = service.redact_pii("тел +7 916 123 45 67 паспорт 4510 123456")
    assert "[PHONE_REDACTED]" in result
    assert "[PASSPORT_REDACTED]" in result


@pytest.mark.unit
def test_redact_sensitive_keys_ru():
    service = RedactionService()
    result = service.redact_sensitive_keys({"токен": "abc", "ok": 1})
    assert result["токен"] == "***REDACTED***"
    assert result["ok"] == 1


@pytest.mark.unit
def test_contains_sensitive_data_ru_key():
    service = RedactionService()
    assert service.contains_sensitive_data("пароль=qwerty")
