from __future__ import annotations

PII_PATTERNS_ZH: list[tuple[str, str]] = [
    (r"\b1[3-9]\d{9}\b", "[PHONE_REDACTED]"),
    (r"\b\d{17}[\dXx]\b", "[ID_REDACTED]"),
]
