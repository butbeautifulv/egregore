from __future__ import annotations

import re
import unicodedata

# Zero-width, bidi overrides, variation selectors.
ZERO_WIDTH_CHARS = re.compile("[\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff\u2066-\u2069\ufe00-\ufe0f]")

# Cyrillic letters that look like Latin (fold to Latin for cross-script matching).
_CYRILLIC_TO_LATIN = str.maketrans(
    {
        "\u0430": "a",
        "\u0435": "e",
        "\u043e": "o",
        "\u0440": "p",
        "\u0441": "c",
        "\u0443": "y",
        "\u0445": "x",
        "\u0410": "a",
        "\u0415": "e",
        "\u041e": "o",
        "\u0420": "p",
        "\u0421": "c",
        "\u0423": "y",
        "\u0425": "x",
    }
)

TOKEN_PATTERN = re.compile(r"[\w\u0400-\u04FF]+", re.UNICODE)

# Unicode tag characters (TOKEN80M8 / TOKENADE-style smuggling; includes E01xx tags).
UNICODE_TAG_CHARS = re.compile("[\U000e0000-\U000e01ef]")

_MIXED_SCRIPT_LATIN = re.compile(r"[A-Za-z]")
_MIXED_SCRIPT_CYRILLIC = re.compile(r"[\u0400-\u04FF]")
_MIXED_SCRIPT_CJK = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff\uac00-\ud7af]")
_MIXED_SCRIPT_GREEK = re.compile(r"[\u0370-\u03ff]")
_MIXED_SCRIPT_MATH = re.compile(r"[\u2100-\u214f\U0001d400-\U0001d7ff]")

# Minimum tag characters before treating input as smuggled-token payload.
UNICODE_TAG_SMUGGLING_THRESHOLD = 12


def strip_combining_marks(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def latin_skeleton_for_detection(text: str) -> str:
    """Strip non-Latin noise between injection markers (GROK-MEGA-style obfuscation)."""
    content = unicodedata.normalize("NFKC", text)
    content = strip_combining_marks(content)
    content = ZERO_WIDTH_CHARS.sub(" ", content)
    content = re.sub(r"[^a-zA-Z0-9<|>!._:\\/\\[\\]{}\\-]+", " ", content)
    return re.sub(r"\s+", " ", content).strip()


def count_unicode_tags(text: str) -> int:
    return len(UNICODE_TAG_CHARS.findall(text))


def mixed_script_category_count(text: str) -> int:
    categories = (
        _MIXED_SCRIPT_LATIN,
        _MIXED_SCRIPT_CYRILLIC,
        _MIXED_SCRIPT_CJK,
        _MIXED_SCRIPT_GREEK,
        _MIXED_SCRIPT_MATH,
    )
    return sum(1 for pattern in categories if pattern.search(text))


def is_mixed_script_smuggling(text: str) -> bool:
    """Heuristic for GROK-MEGA-style homoglyph / multi-script obfuscation."""
    if len(text) < 180:
        return False
    non_ascii = sum(1 for ch in text if ord(ch) > 127)
    if non_ascii / len(text) < 0.45:
        return False
    return mixed_script_category_count(text) >= 3


def fold_confusables(text: str) -> str:
    """Map Cyrillic homoglyphs to Latin only in mixed-script tokens (e.g. ignоre)."""
    tokens = TOKEN_PATTERN.findall(text)
    if not tokens:
        return text
    result = text
    for token in tokens:
        has_ascii = any("A" <= ch <= "Z" or "a" <= ch <= "z" for ch in token)
        has_cyrillic = any("\u0400" <= ch <= "\u04ff" for ch in token)
        if has_ascii and has_cyrillic:
            folded = token.translate(_CYRILLIC_TO_LATIN)
            if folded != token:
                result = result.replace(token, folded, 1)
    return result


def normalize_input(content: str) -> str:
    """Full normalization pipeline for injection detection."""
    content = unicodedata.normalize("NFKC", content)
    content = ZERO_WIDTH_CHARS.sub(" ", content)
    content = fold_confusables(content)
    content = re.sub(r"\s+", " ", content)
    content = re.sub(r"(.)\1{3,}", r"\1", content)
    return content.strip()
