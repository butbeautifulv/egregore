from __future__ import annotations

PII_PATTERNS_ES: list[tuple[str, str]] = [
    (r"\b\d{8}[A-Za-z]\b", "[DNI_REDACTED]"),
    (r"\b[XYZ]\d{7}[A-Za-z]\b", "[NIE_REDACTED]"),
]
