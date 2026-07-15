from __future__ import annotations

from functools import lru_cache

from cys_core.domain.security.guardrails import OutputGuardrails
from cys_core.domain.security.sanitizer import InputSanitizer


@lru_cache
def get_input_sanitizer() -> InputSanitizer:
    return InputSanitizer()


@lru_cache
def get_output_guardrails() -> OutputGuardrails:
    return OutputGuardrails()
