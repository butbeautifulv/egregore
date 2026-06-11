from __future__ import annotations

import re
from typing import Any

from cys_core.domain.security.patterns import PII_PATTERNS, SENSITIVE_KEYS

# Patterns used by contains_sensitive_data (subset for fast checks).
_SENSITIVE_DATA_PATTERNS = tuple(pattern for pattern, _ in PII_PATTERNS)


class RedactionService:
    """PII and sensitive-key redaction policies."""

    def redact_pii(self, text: str) -> str:
        for pattern, replacement in PII_PATTERNS:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        return text

    def redact_sensitive_keys(self, data: Any) -> Any:
        if isinstance(data, dict):
            return {
                k: "***REDACTED***" if k.lower() in SENSITIVE_KEYS else self.redact_sensitive_keys(v)
                for k, v in data.items()
            }
        if isinstance(data, list):
            return [self.redact_sensitive_keys(item) for item in data]
        return data

    def contains_sensitive_data(self, text: str) -> bool:
        return any(re.search(pattern, text, re.IGNORECASE) for pattern in _SENSITIVE_DATA_PATTERNS)
