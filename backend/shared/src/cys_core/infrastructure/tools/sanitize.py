from __future__ import annotations

import json
from typing import Any

from cys_core.domain.security.content_delimiters import wrap_retrieved_tool_data
from cys_core.domain.security.exceptions import SecurityViolation
from cys_core.domain.security.factory import get_input_sanitizer
from cys_core.domain.security.sanitizer import InputSanitizer
from cys_core.observability.metrics import metrics


def sanitize_tool_output(raw: Any, sanitizer: InputSanitizer | None = None) -> str:
    """Sanitize untrusted MCP/tool output and wrap with retrieval delimiters."""
    san = sanitizer or get_input_sanitizer()
    if isinstance(raw, dict):
        text = json.dumps(raw, ensure_ascii=False)
    elif isinstance(raw, str):
        text = raw
    else:
        text = str(raw)
    sanitized = san.sanitize(text, source="tool")
    return wrap_retrieved_tool_data(sanitized)


def sanitize_tool_output_or_raise(raw: Any, sanitizer: InputSanitizer | None = None) -> str:
    try:
        return sanitize_tool_output(raw, sanitizer=sanitizer)
    except SecurityViolation as exc:
        metrics.record_sanitizer_block("tool", "hard")
        raise SecurityViolation(f"Poisoned tool response blocked: {exc}") from exc
