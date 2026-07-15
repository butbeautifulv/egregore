from __future__ import annotations

import base64
import binascii
import re
from enum import Enum
from typing import Any

from rapidfuzz.distance import Levenshtein

from cys_core.domain.security.exceptions import SecurityViolation
from cys_core.domain.security.patterns import (
    BASE64_TOKEN,
    FUZZY_DISTANCE_THRESHOLD,
    FUZZY_KEYWORDS,
    FUZZY_KEYWORDS_EN,
    FUZZY_KEYWORDS_RU,
    HARD_INJECTION_PATTERNS,
    HEX_TOKEN,
    INJECTION_PATTERNS,
    MIN_FUZZY_WORD_LENGTH,
    SOFT_INJECTION_PATTERNS,
    TOKEN_PATTERN,
    UNICODE_TAG_SMUGGLING_THRESHOLD,
    count_unicode_tags,
    is_mixed_script_smuggling,
    latin_skeleton_for_detection,
    normalize_input,
)
from cys_core.domain.security.prompt_context import UntrustedSource, wrap_user_data

MAX_INPUT_LENGTH = 50_000
FILTERED_MARKER = "[FILTERED_INJECTION]"


class InjectionVerdict(str, Enum):
    NONE = "none"
    SOFT = "soft"
    HARD = "hard"


class InputSanitizer:
    """Sanitize untrusted input before it enters agent context."""

    def __init__(self, max_length: int = MAX_INPUT_LENGTH) -> None:
        self.max_length = max_length
        self._hard = [re.compile(p, re.IGNORECASE) for p in HARD_INJECTION_PATTERNS]
        self._soft = [re.compile(p, re.IGNORECASE) for p in SOFT_INJECTION_PATTERNS]
        self._all = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]

    def classify(self, content: str) -> InjectionVerdict:
        normalized = self._normalize(content)
        skeleton = latin_skeleton_for_detection(content)
        candidates = [normalized]
        if skeleton and skeleton != normalized:
            candidates.append(skeleton)
        if self._matches_any_hard(candidates):
            return InjectionVerdict.HARD
        if self._matches_encoded_hard(content) or any(
            self._matches_encoded_hard(candidate) for candidate in candidates
        ):
            return InjectionVerdict.HARD
        if self._has_unicode_tag_smuggling(content) or is_mixed_script_smuggling(content):
            return InjectionVerdict.SOFT
        if self._matches_any_soft(candidates) or any(self._matches_fuzzy(candidate) for candidate in candidates):
            return InjectionVerdict.SOFT
        if self._matches_encoded_soft(content) or any(
            self._matches_encoded_soft(candidate) for candidate in candidates
        ):
            return InjectionVerdict.SOFT
        return InjectionVerdict.NONE

    def sanitize(self, content: str, *, source: UntrustedSource = "user") -> str:
        if content.strip().startswith("USER_DATA_TO_PROCESS"):
            return content
        verdict = self.classify(content)
        if verdict is InjectionVerdict.HARD:
            raise SecurityViolation("Prompt injection detected in untrusted input")
        body = self._normalize(content)
        if len(body) > self.max_length:
            body = body[: self.max_length]
        for pattern in self._all:
            body = pattern.sub(FILTERED_MARKER, body)
        return self.wrap_untrusted(body, source=source)

    @staticmethod
    def wrap_untrusted(content: str, *, source: UntrustedSource = "user") -> str:
        if content.strip().startswith("USER_DATA_TO_PROCESS"):
            return content
        return wrap_user_data(content, source=source)

    def sanitize_payload(self, payload: dict[str, Any], *, source: UntrustedSource = "user") -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in payload.items():
            if isinstance(value, str):
                result[key] = self.sanitize(value, source=source)
            elif isinstance(value, dict):
                result[key] = self.sanitize_payload(value, source=source)
            elif isinstance(value, list):
                result[key] = [self.sanitize(v, source=source) if isinstance(v, str) else v for v in value]
            else:
                result[key] = value
        return result

    def filter_patterns(self, content: str) -> str:
        """Replace injection patterns without wrapping (internal storage paths)."""
        body = self._normalize(content)
        if len(body) > self.max_length:
            body = body[: self.max_length]
        for pattern in self._all:
            body = pattern.sub(FILTERED_MARKER, body)
        return body

    def filter_untrusted(self, content: str, *, source: UntrustedSource = "user") -> str:
        """Filter and wrap without blocking (internal transports)."""
        if content.strip().startswith("USER_DATA_TO_PROCESS"):
            return content
        body = self._normalize(content)
        if len(body) > self.max_length:
            body = body[: self.max_length]
        for pattern in self._all:
            body = pattern.sub(FILTERED_MARKER, body)
        return self.wrap_untrusted(body, source=source)

    def _normalize(self, content: str) -> str:
        return normalize_input(content)

    def _matches_hard(self, content: str) -> bool:
        return any(p.search(content) for p in self._hard)

    def _matches_soft(self, content: str) -> bool:
        return any(p.search(content) for p in self._soft)

    def _matches_any_hard(self, candidates: list[str]) -> bool:
        return any(self._matches_hard(candidate) for candidate in candidates)

    def _matches_any_soft(self, candidates: list[str]) -> bool:
        return any(self._matches_soft(candidate) for candidate in candidates)

    @staticmethod
    def _has_unicode_tag_smuggling(content: str) -> bool:
        return count_unicode_tags(content) >= UNICODE_TAG_SMUGGLING_THRESHOLD

    def _matches_fuzzy(self, content: str) -> bool:
        words = TOKEN_PATTERN.findall(content.lower())
        for word in words:
            if len(word) < MIN_FUZZY_WORD_LENGTH:
                continue
            if self._fuzzy_match_keyword_set(word, FUZZY_KEYWORDS):
                return True
        return False

    @staticmethod
    def _fuzzy_match_keyword_set(word: str, keywords: frozenset[str]) -> bool:
        for keyword in keywords:
            if Levenshtein.distance(word, keyword) <= FUZZY_DISTANCE_THRESHOLD:
                return True
        return False

    def _matches_encoded_hard(self, content: str) -> bool:
        for decoded in self._decode_candidates(content):
            if self._matches_hard(self._normalize(decoded)):
                return True
        return False

    def _matches_encoded_soft(self, content: str) -> bool:
        for decoded in self._decode_candidates(content):
            normalized = self._normalize(decoded)
            if self._matches_soft(normalized) or self._matches_fuzzy(normalized):
                return True
        return False

    def _decode_candidates(self, content: str) -> list[str]:
        candidates: list[str] = []
        for match in BASE64_TOKEN.findall(content):
            try:
                decoded = base64.b64decode(match, validate=True).decode("utf-8", errors="ignore")
                if decoded.strip():
                    candidates.append(decoded)
            except (binascii.Error, ValueError):
                continue
        for match in HEX_TOKEN.findall(content):
            try:
                decoded = bytes.fromhex(match).decode("utf-8", errors="ignore")
                if decoded.strip():
                    candidates.append(decoded)
            except ValueError:
                continue
        return candidates


# Re-export for backward compatibility in tests.
__all__ = [
    "FILTERED_MARKER",
    "FUZZY_KEYWORDS",
    "FUZZY_KEYWORDS_EN",
    "FUZZY_KEYWORDS_RU",
    "InjectionVerdict",
    "InputSanitizer",
    "MAX_INPUT_LENGTH",
]
