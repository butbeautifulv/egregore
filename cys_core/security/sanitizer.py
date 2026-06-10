from __future__ import annotations

import re
from typing import Any

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
    r"disregard\s+(all\s+)?(previous|prior|system)\s+",
    r"you\s+are\s+now\s+",
    r"new\s+system\s+prompt",
    r"<\s*/?\s*system\s*>",
    r"\[INST\]",
    r"###\s*instruction",
]

MAX_INPUT_LENGTH = 50_000


class InputSanitizer:
    """Sanitize untrusted input before agent context (cheat sheet §2)."""

    def __init__(self, max_length: int = MAX_INPUT_LENGTH) -> None:
        self.max_length = max_length
        self._compiled = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]

    def sanitize(self, content: str) -> str:
        if len(content) > self.max_length:
            content = content[: self.max_length]
        for pattern in self._compiled:
            content = pattern.sub("[FILTERED_INJECTION]", content)
        return self.wrap_untrusted(content)

    @staticmethod
    def wrap_untrusted(content: str) -> str:
        return f"<untrusted_data>\n{content}\n</untrusted_data>"

    def sanitize_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in payload.items():
            if isinstance(value, str):
                result[key] = self.sanitize(value)
            elif isinstance(value, dict):
                result[key] = self.sanitize_payload(value)
            elif isinstance(value, list):
                result[key] = [
                    self.sanitize(v) if isinstance(v, str) else v for v in value
                ]
            else:
                result[key] = value
        return result
