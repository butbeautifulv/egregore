from __future__ import annotations

PII_PATTERNS_EN: list[tuple[str, str]] = [
    (r"\b\d{3}-\d{2}-\d{4}\b", "[SSN_REDACTED]"),
    (r"\b\d{16}\b", "[CARD_REDACTED]"),
]
