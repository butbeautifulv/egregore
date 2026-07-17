from __future__ import annotations

PII_PATTERNS_COMMON: list[tuple[str, str]] = [
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", "[EMAIL_REDACTED]"),
    (r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "[IP_REDACTED]"),
]

SENSITIVE_KEY_PATTERNS_COMMON: list[tuple[str, str]] = [
    (r"password\s*[:=]\s*\S+", "password=[REDACTED]"),
    (r"api[_-]?key\s*[:=]\s*\S+", "api_key=[REDACTED]"),
    (r"secret\s*[:=]\s*\S+", "secret=[REDACTED]"),
    (r"token\s*[:=]\s*\S+", "token=[REDACTED]"),
]
