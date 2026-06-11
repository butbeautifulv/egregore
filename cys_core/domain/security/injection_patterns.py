from __future__ import annotations

"""Backward-compatible re-exports. Prefer cys_core.domain.security.patterns."""

from cys_core.domain.security.patterns import (
    BASE64_TOKEN,
    FUZZY_DISTANCE_THRESHOLD,
    FUZZY_KEYWORDS,
    HARD_INJECTION_PATTERNS,
    HEX_TOKEN,
    INJECTION_PATTERNS,
    MIN_FUZZY_WORD_LENGTH,
    SOFT_INJECTION_PATTERNS,
    ZERO_WIDTH_CHARS,
)

__all__ = [
    "BASE64_TOKEN",
    "FUZZY_DISTANCE_THRESHOLD",
    "FUZZY_KEYWORDS",
    "HARD_INJECTION_PATTERNS",
    "HEX_TOKEN",
    "INJECTION_PATTERNS",
    "MIN_FUZZY_WORD_LENGTH",
    "SOFT_INJECTION_PATTERNS",
    "ZERO_WIDTH_CHARS",
]
